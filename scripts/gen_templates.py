#!/usr/bin/env python3
from __future__ import annotations
from k1.modules.generators.nuclei_from_cve import generate_http_template
SAMPLES = [
    ("CVE-2021-29447", "wordpress-xss", "/wp-admin/readme.html"),
    ("CVE-2020-14882", "weblogic-console", "/console/login/LoginForm.jsp"),
    ("CVE-2019-7609", "kibana-timelion-rce", "/app/kibana"),
    ("CVE-2018-11776", "struts-s2-057", "/"),
    ("CVE-2022-26134", "confluence-ognl", "/"),
    ("CVE-2021-44228", "log4shell", "/"),
    ("CVE-2023-3519", "netscaler-gateway", "/"),
    ("CVE-2017-5638", "struts-s2-045", "/"),
    ("CVE-2021-26855", "exchange-proxylogon", "/owa/"),
    ("CVE-2020-2551", "weblogic-iiop", "/"),
]
if __name__ == "__main__":
    for cve, name, path in SAMPLES:
        print(generate_http_template(cve, name, path))
