"""Unit checks for the native CI theme/mail assertions, without Docker or SMTP."""
from email.message import EmailMessage
import importlib.util
from pathlib import Path
import unittest
from unittest.mock import Mock

ROOT = Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location('keycloak_runtime', ROOT / 'tests/deploy/keycloak-runtime.py')
RUNTIME = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(RUNTIME)


class KeycloakRuntimeThemeTests(unittest.TestCase):
    def page(self, theme='sihsalus', color_scheme='light'):
        resource = RUNTIME.BASE + '/resources/test/login/' + theme + '/css/'
        return RUNTIME.Page(
            '<meta name="color-scheme" content="' + color_scheme + '">'
            '<link rel="stylesheet" href="' + resource + 'styles.css">'
            '<link rel="stylesheet" href="' + resource + 'sihsalus.css">'
            '<body id="keycloak-bg"><form id="kc-form-login"><input name="username"></form></body>',
            RUNTIME.BASE + '/login', 200)

    def test_theme_assertion_fetches_both_real_resource_urls_and_preserves_form_parser(self):
        page = self.page()
        browser = Mock()
        browser.request.side_effect = [
            RUNTIME.Page('.pf-v5-c-login__container {}', page.stylesheets[0], 200),
            RUNTIME.Page('--sihsalus-primary: #4836ff;', page.stylesheets[1], 200)]
        RUNTIME.verify_theme(browser, page)
        self.assertEqual([call.args[0] for call in browser.request.call_args_list], page.stylesheets)
        self.assertIn('username', page.forms['kc-form-login']['fields'])

    def test_missing_theme_or_unexpected_dark_variant_fails(self):
        for page in (self.page(theme='keycloak.v2'), self.page(color_scheme='light dark')):
            with self.subTest(styles=page.stylesheets, scheme=page.color_scheme), self.assertRaises(AssertionError):
                RUNTIME.verify_theme(Mock(), page)

    def test_missing_packaged_stylesheet_fails(self):
        browser = Mock()
        browser.request.return_value = RUNTIME.Page('Not found', '', 404)
        with self.assertRaisesRegex(AssertionError, 'resource missing'):
            RUNTIME.verify_theme(browser, self.page())

    def mailbox(self, plain_duration='30 minutos', html_duration='30 minutos'):
        message = EmailMessage()
        message['Subject'] = 'Verifica tu correo electrónico'
        link = RUNTIME.BASE + '/realms/ocl/login-actions/action-token?key=synthetic'
        message.set_content('El enlace caduca en ' + plain_duration + '.\n\n' + link)
        message.add_alternative('<p>El enlace caduca en ' + html_duration + '.</p><a href="' + link + '">Verificar</a>', subtype='html')
        mailbox = RUNTIME.Mailbox()
        mailbox.messages.append((('synthetic@pucp.edu.pe',), message.as_bytes()))
        return mailbox, link

    def test_mail_assertion_accepts_native_duration_and_preserves_verification_link(self):
        mailbox, link = self.mailbox()
        self.assertEqual(mailbox.link('synthetic@pucp.edu.pe', 0,
                                      expected_subject='Verifica tu correo electrónico'), link)

    def test_mail_assertion_checks_plain_text_and_html_before_returning_link(self):
        for plain, html in (('30 minutos minutos', '30 minutos'), ('30 minutos', '30 minutos minutos')):
            mailbox, _ = self.mailbox(plain, html)
            with self.subTest(plain=plain, html=html), self.assertRaisesRegex(AssertionError, 'duration'):
                mailbox.link('synthetic@pucp.edu.pe', 0)


if __name__ == '__main__':
    unittest.main()
