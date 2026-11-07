"""Drive only the synthetic Keycloak login/consent; never replace client OAuth."""

from urllib.parse import urljoin, urlsplit

import httpx
from bs4 import BeautifulSoup


def keycloak_browser(lab, url, who):
    origin_parts = urlsplit(lab.issuer)
    origin = f"{origin_parts.scheme}://{origin_parts.netloc}"
    with httpx.Client(verify=lab.tls, trust_env=False, timeout=30) as browser:
        for _ in range(30):
            if not url.startswith(lab.issuer + "/"):
                return url
            response = browser.get(url)
            if response.is_redirect:
                url = urljoin(url, response.headers["location"])
                continue
            response.raise_for_status()
            document = BeautifulSoup(response.text, "html.parser")
            form = next(
                (
                    form
                    for form in document.select("form")
                    if form.select_one("[name=password], [name=accept]")
                ),
                None,
            )
            assert form is not None, (
                "Unexpected Keycloak interaction: "
                f"title={document.title.get_text(strip=True) if document.title else ''}; "
                f"forms={[f.get('id') for f in document.select('form')]}"
            )
            fields = {
                i["name"]: i.get("value", "")
                for i in form.select("input[name]")
                if i.get("type") not in ("submit", "button")
            }
            if form.select_one("[name=password]"):
                fields.update(username=who, password=lab.oidc_passwords[who])
            else:
                fields["accept"] = "Yes"
            target = urljoin(url, form["action"])
            response = browser.post(target, data=fields, headers={"Origin": origin})
            assert response.is_redirect, (
                f"Keycloak form failed ({response.status_code})"
            )
            url = urljoin(target, response.headers["location"])
    raise AssertionError("Keycloak interaction redirect loop")
