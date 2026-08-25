import argparse
import io
import json
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

import core.cnki  # noqa: E402
from cli.cnki_cmd import cmd_auth_cnki  # noqa: E402
from core.cnki import driver  # noqa: E402


class FakeDriver:
    def __init__(self, text=""):
        self.visited = []
        self.saved = False
        self.closed = False
        self.cookies_cleared = False
        self.current_url = "https://kns.cnki.net/"
        self.title = "中国知网"
        self.text = text

    def get(self, url):
        self.visited.append(url)
        self.current_url = url

    def execute_script(self, script):
        if "querySelectorAll('a')" in script:
            return []
        return self.text

    def get_cookies(self):
        return [{"name": "Ecp_ClientId", "domain": ".cnki.net"}]

    def delete_all_cookies(self):
        self.cookies_cleared = True

    def quit(self):
        self.closed = True


class LinkDriver(FakeDriver):
    def execute_script(self, script):
        if "querySelectorAll('a')" in script:
            return [
                {"text": "Example University", "href": "https://idp.example.edu/login"},
                {"text": "Other School", "href": "https://idp.other.edu/login"},
            ]
        return super().execute_script(script)


class CnkiAuthFlowTests(unittest.TestCase):
    def test_proxy_bypass_includes_cnki_carsi_and_custom_domains(self):
        with patch.dict(
            "os.environ",
            {"HUMLIT_CNKI_DIRECT_DOMAINS": "*.school.edu.cn;idp.example.edu"},
            clear=False,
        ):
            domains = driver._cnki_proxy_bypass_domains(["vpn.example.edu,library.example.edu"])

        self.assertIn("*.cnki.net", domains)
        self.assertIn("*.carsi.edu.cn", domains)
        self.assertIn("fsso.cnki.net", domains)
        self.assertIn("*.school.edu.cn", domains)
        self.assertIn("idp.example.edu", domains)
        self.assertIn("vpn.example.edu", domains)
        self.assertIn("library.example.edu", domains)
        self.assertEqual(domains.count("*.cnki.net"), 1)

    def test_select_cnki_institution_is_optional_and_generic(self):
        fake = LinkDriver()

        selected = driver._select_cnki_institution(fake, "Example University")

        self.assertTrue(selected)
        self.assertEqual(fake.visited[-1], "https://idp.example.edu/login")

    def test_select_cnki_institution_does_nothing_when_not_explicit(self):
        fake = LinkDriver()

        selected = driver._select_cnki_institution(fake, None)

        self.assertFalse(selected)
        self.assertEqual(fake.visited, [])

    def test_profile_debug_port_is_read_from_active_marker(self):
        with tempfile.TemporaryDirectory() as raw_dir:
            profile = Path(raw_dir)
            (profile / "DevToolsActivePort").write_text(
                "12345\n/devtools/browser/test\n", encoding="utf-8"
            )

            self.assertEqual(driver._debug_port_from_profile(profile), 12345)

    def test_existing_profile_is_reused_before_new_browser_launch(self):
        class RemoteSentinel:
            pass

        sentinel = RemoteSentinel()
        with tempfile.TemporaryDirectory() as raw_dir:
            profile = Path(raw_dir)
            (profile / "DevToolsActivePort").write_text("12345\n", encoding="utf-8")
            with patch.object(driver, "_wait_for_debug_port", return_value=True), \
                 patch.object(driver, "_connect_remote_browser", return_value=sentinel) as connect:
                result = driver._try_connect_existing_profile("edge", profile)

        self.assertIs(result, sentinel)
        self.assertTrue(sentinel._humlit_reused)
        connect.assert_called_once_with("edge", 12345)

    def test_authenticate_cnki_reuses_existing_session_without_login(self):
        fake = FakeDriver(text="机构馆 个人中心 我的知网")

        with patch.object(driver, "_detect_browser", return_value="chrome"), \
             patch.object(driver, "_create_driver", return_value=fake), \
             patch.object(driver, "_show_browser"), \
             patch.object(driver, "_hide_browser"), \
             patch.object(driver, "_load_cookies"), \
             patch.object(driver, "_save_cookies", side_effect=lambda d: setattr(d, "saved", True) or True):
            result = driver.authenticate_cnki(
                auth_url="https://fsso.cnki.net/",
                verify_url="https://kns.cnki.net/",
                wait_seconds=30,
                reuse_session=True,
            )

        self.assertEqual(result["status"], "success")
        self.assertTrue(result["already_authenticated"])
        self.assertTrue(result["session_reused"])
        self.assertTrue(result["access_confirmed"])
        self.assertTrue(result["cookies_saved"])
        self.assertEqual(fake.visited, ["https://kns.cnki.net/", "https://kns.cnki.net/"])
        self.assertTrue(fake.closed)

    def test_authenticate_defaults_to_manual_flow_without_reusing_local_session(self):
        fake = FakeDriver(text="机构馆 个人中心 我的知网")

        with patch.object(driver, "_detect_browser", return_value="chrome"), \
             patch.object(driver, "_create_driver", return_value=fake), \
             patch.object(driver, "_show_browser"), \
             patch.object(driver, "_hide_browser"), \
             patch.object(driver, "_load_cookies") as load_cookies, \
             patch.object(driver, "_save_cookies", return_value=True):
            result = driver.authenticate_cnki(
                auth_url="https://fsso.cnki.net/",
                verify_url="https://kns.cnki.net/",
                wait_seconds=0,
            )

        self.assertFalse(result["already_authenticated"])
        self.assertFalse(result["session_reused"])
        self.assertTrue(fake.cookies_cleared)
        load_cookies.assert_not_called()
        self.assertIn("https://fsso.cnki.net/", fake.visited)

    def test_keep_browser_requests_detached_browser_process(self):
        fake = FakeDriver(text="")

        with patch.object(driver, "_detect_browser", return_value="chrome"), \
             patch.object(driver, "_create_driver", return_value=fake) as create_driver, \
             patch.object(driver, "_show_browser"), \
             patch.object(driver, "_hide_browser"), \
             patch.object(driver, "_save_cookies", return_value=True):
            driver.authenticate_cnki(wait_seconds=0, keep_browser=True)

        create_driver.assert_called_once_with(browser="chrome", detach=True)
        self.assertFalse(fake.closed)

    def test_common_cnki_navigation_text_is_not_institution_access(self):
        fake = FakeDriver(text="个人中心 我的知网 退出")

        self.assertFalse(driver._has_cnki_institution_access(fake))

    def test_institution_name_confirms_access_only_on_cnki_url(self):
        fake = FakeDriver(text="Example University")
        fake.current_url = "https://idp.example.edu/login"
        self.assertFalse(driver._has_cnki_institution_access(fake, institution="Example University"))

        fake.current_url = "https://kns.cnki.net/"
        self.assertTrue(driver._has_cnki_institution_access(fake, institution="Example University"))

    def test_manual_institution_label_confirms_access_without_institution_argument(self):
        fake = FakeDriver(text="暨南大学 个人登录")

        self.assertTrue(driver._has_cnki_institution_access(fake))

    def test_manual_institution_label_can_span_adjacent_header_lines(self):
        fake = FakeDriver(text="示例大学\n服务入口\n个人登录")

        self.assertTrue(driver._has_cnki_institution_access(fake))

    def test_fsso_institution_picker_is_not_treated_as_authenticated(self):
        fake = FakeDriver(text="选择学校或机构\n个人登录")
        fake.current_url = "https://fsso.cnki.net/"

        self.assertFalse(driver._has_cnki_institution_access(fake))

    def test_generic_personal_login_does_not_confirm_institution_access(self):
        fake = FakeDriver(text="个人登录")

        self.assertFalse(driver._has_cnki_institution_access(fake))

    def test_hidden_security_marker_does_not_keep_gate_open(self):
        class HiddenMarkerDriver(FakeDriver):
            def execute_script(self, script, *args):
                if "getBoundingClientRect" in script:
                    return False
                return super().execute_script(script)

        fake = HiddenMarkerDriver(text="拖动下方拼图完成验证")

        self.assertFalse(driver._is_cnki_security_gate(fake))

    def test_security_gate_detects_captcha_id_intermediate_url(self):
        fake = FakeDriver(text="")
        fake.current_url = "https://kns.cnki.net/kns8s/search?captchaId=challenge"

        self.assertTrue(driver._is_cnki_security_gate(fake))

    def test_stale_captcha_id_is_not_gate_when_search_surface_is_ready(self):
        class ReadyDriver(FakeDriver):
            def implicitly_wait(self, seconds):
                pass

            def find_elements(self, by, selector):
                return [object()] if selector == "#txt_search" else []

            def execute_script(self, script, *args):
                if "getBoundingClientRect" in script:
                    return False
                return super().execute_script(script)

        fake = ReadyDriver(text="中国知网 一框式检索")
        fake.current_url = "https://kns.cnki.net/kns8s/search?captchaId=completed"

        self.assertFalse(driver._is_cnki_security_gate(fake))

    def test_security_gate_detects_slider_text_on_search_page(self):
        fake = FakeDriver(text="抱歉，暂无数据，请稍后重试。拖动下方拼图完成验证")

        self.assertTrue(driver._is_cnki_security_gate(fake))

    def test_captcha_timeout_is_structured_and_not_swallowed(self):
        fake = FakeDriver()
        fake.current_url = "https://kns.cnki.net/verify/challenge"

        with patch.object(driver, "_show_browser"), \
             patch.object(driver, "_save_cookies"):
            with self.assertRaises(driver.CnkiSecurityError) as raised:
                driver._show_browser_for_captcha(fake, poll_timeout=0)

        self.assertEqual(raised.exception.code, "CNKI_SECURITY_GATE_TIMEOUT")

    def test_handle_captcha_propagates_security_timeout(self):
        fake = FakeDriver()
        error = driver.CnkiSecurityError("CNKI_SECURITY_GATE_TIMEOUT", "verification timed out")

        with patch.object(driver, "_is_cnki_security_gate", return_value=True), \
             patch.object(driver, "_show_browser_for_captcha", side_effect=error):
            with self.assertRaises(driver.CnkiSecurityError) as raised:
                driver._handle_captcha(fake)

        self.assertEqual(raised.exception.code, "CNKI_SECURITY_GATE_TIMEOUT")

    def test_cmd_auth_cnki_outputs_json_and_passes_generic_options(self):
        with patch.object(
            core.cnki,
            "authenticate_cnki",
            return_value={
                "status": "success",
                "access_confirmed": True,
                "direct_domains": ["idp.example.edu"],
            },
        ) as auth:
            out = io.StringIO()
            with redirect_stdout(out):
                cmd_auth_cnki(
                    argparse.Namespace(
                        auth_url="https://library.example.edu/cnki",
                        verify_url="https://kns.cnki.net/",
                        institution=None,
                        wait_seconds=120,
                        captcha_timeout=60,
                        direct_domain=["idp.example.edu"],
                        debug_snapshot=None,
                        keep_browser=True,
                        force=True,
                    )
                )

        data = json.loads(out.getvalue())
        self.assertEqual(data["status"], "success")
        auth.assert_called_once()
        self.assertTrue(auth.call_args.kwargs["keep_browser"])
        self.assertTrue(auth.call_args.kwargs["force"])
        self.assertFalse(auth.call_args.kwargs["reuse_session"])
        self.assertEqual(auth.call_args.kwargs["direct_domains"], ["idp.example.edu"])

    def test_security_verification_keeps_browser_visible_after_success(self):
        fake = FakeDriver()
        with patch.object(driver, "_show_browser"), \
             patch.object(driver, "_hide_browser") as hide_browser, \
             patch.object(driver, "_save_cookies"), \
             patch.object(driver, "_is_cnki_security_gate", side_effect=[True, False, False]), \
             patch.object(driver.time, "sleep"):
            driver._show_browser_for_captcha(fake, poll_timeout=1)

        hide_browser.assert_not_called()

    def test_wait_for_auth_propagates_security_timeout_without_second_login_cycle(self):
        fake = FakeDriver()
        error = driver.CnkiSecurityError("CNKI_SECURITY_GATE_TIMEOUT", "timed out")

        with patch.object(driver, "_is_cnki_security_gate", return_value=True), \
             patch.object(driver, "_show_browser_for_captcha", side_effect=error):
            with self.assertRaises(driver.CnkiSecurityError) as raised:
                driver._wait_for_cnki_auth(
                    fake,
                    verify_url="https://kns.cnki.net/",
                    institution=None,
                    wait_seconds=10,
                )

        self.assertEqual(raised.exception.code, "CNKI_SECURITY_GATE_TIMEOUT")

    def test_confirmed_auth_does_not_reload_verify_page(self):
        fake = FakeDriver(text="示例大学\n个人登录")

        def finish_login(*args, **kwargs):
            fake.current_url = "https://kns.cnki.net/kns8s/defaultresult/index"
            return True

        with patch.object(driver, "_detect_browser", return_value="chrome"), \
             patch.object(driver, "_create_driver", return_value=fake), \
             patch.object(driver, "_show_browser"), \
             patch.object(driver, "_hide_browser"), \
             patch.object(driver, "_wait_for_cnki_auth", side_effect=finish_login), \
             patch.object(driver, "_is_cnki_security_gate", return_value=False), \
             patch.object(driver, "_has_captcha_elements", return_value=False), \
             patch.object(driver, "_save_cookies", return_value=True):
            result = driver.authenticate_cnki(wait_seconds=30)

        self.assertTrue(result["access_confirmed"])
        self.assertEqual(fake.visited.count("https://kns.cnki.net/"), 3)


if __name__ == "__main__":
    unittest.main()
