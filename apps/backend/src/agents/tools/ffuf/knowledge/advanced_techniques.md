# FFUF Advanced Techniques

## Directory Mode
`ffuf -u https://target/FUZZ -w wordlist -mc 200,201,204,301,302,401,403 -of json`

## VHost Mode
`ffuf -u https://target -H "Host: FUZZ.domain.tld" -w subdomain_wordlist -mc 200`

## WAF Adaptive Profile
Use low thread/rate settings under WAF (`-t 5 -rate 2`), and higher baseline threads when no WAF pressure is observed.

## Wordlist Strategy
Select directory/file vs DNS/vhost wordlists based on target mode to reduce irrelevant results.
