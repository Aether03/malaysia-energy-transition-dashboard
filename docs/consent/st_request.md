# Energy Commission consent request (task 6.1, pulled into M5)

**To:** sc@st.gov.my (Strategic Communications, from the "Who To Contact" page, https://www.st.gov.my/contact-us/who-to-contact; the handbook names the Energy Data and Research Unit, Strategic Planning and Communication Department, as the contact for its figures, but publishes no email for it, and the site's general form is CAPTCHA-protected)
**Subject:** Request for written consent: derived charts from the Malaysia Energy Statistics Handbook 2023 in a non-commercial portfolio project
**Status:** **GRANTED 2026-10-09** (reply in the resent thread; conditions in `DATA_LICENSES.md` §D5). D5 `consent_status = GRANTED` in `seed/data_source.csv`; `is_publishable` stays 0 (the consent covers charts, not the data rows). P3/P3b are now in the published exports (M5 Q2 reversed). First sent 2026-10-07 from amirulaqmalazhar@gmail.com (Gmail message 1a1120fcdce4d462), with Amirul's go.

---

Dear Strategic Communications team,

Could you kindly forward this request to the Energy Data and Research Unit, Strategic Planning and Communication Department, which the Malaysia Energy Statistics Handbook 2023 names as the contact for its figures?

I am a recent Electrical Engineering graduate of Universiti Teknologi MARA (UiTM), and I am building a non-commercial data-analytics portfolio project on Malaysia's electricity transition. The handbook's copyright page states that reproduction of any part of the publication requires the Energy Commission's prior written consent, so I am writing to request that consent before anything is published.

**What the project uses from the handbook (2023 edition)**
- Installed and available capacity by region (pp. 13-14)
- Key economic and energy data by region: electricity consumption and use per person (pp. 17-19)
- Number of supply interruptions by region (p. 82)
- SAIDI and SAIFI by Peninsular state, and Sabah and Sarawak distribution performance (pp. 83-85)

**How it is used**
- A script downloads the public PDF from www.st.gov.my when the project is built. The PDF and the extracted tables are never stored in or redistributed through the public repository.
- The project shows only derived charts: a Peninsular Malaysia vs Sabah vs Sarawak comparison, a state reliability map and ranking, and trends since 2015. It does not reproduce the handbook's tables.
- Every chart is credited "Source: Energy Commission, Malaysia Energy Statistics Handbook 2023", as the copyright page asks, together with a notice that permission has been requested.

**What I am asking for**
Written consent to publish these derived charts, as screenshots, a PDF export and a short video walkthrough, in a public GitHub repository and on my personal portfolio website, for non-commercial purposes only. Until I hear from you, those two report pages are left out of everything I publish.

I am happy to follow any conditions you set, such as specific attribution wording or a review of the pages before they are published.

One observation that may be useful to the unit: in the 2023 edition, the year header of the Sarawak distribution performance table (p. 85) appears to run one year earlier than the matching table in the 2022 edition. I can share the details if helpful.

Thank you for your time and for making these statistics available.

Yours sincerely,
Amirul
Electrical Engineering graduate, UiTM
amirulaqmalazhar@gmail.com
GitHub: https://github.com/Aether03

## Log

- 2026-10-07: sent to sc@st.gov.my, asking them to forward it.
- 2026-10-07: the Strategic Communications Section replied that the request should go directly to two named officers of the Energy Data and Research Unit. Resent the same day with the same text and a first paragraph explaining the redirect (addresses not recorded here: they are personal).
- 2026-10-09: Strategic Communications (Senior Assistant Director) approved the use and adaptation of the handbook's charts and data for the stated purpose, on four conditions: credit "Source: Energy Commission", identify adapted charts, present the data accurately, imply no endorsement. Other uses need separate permission.
- 2026-10-10: thank-you reply sent in the same thread (Gmail message 1a125e9ac4e19626), with Amirul's go; it confirms the four conditions and offers the link once the repository is public.
- 2026-10-11: follow-up sent in the same thread (Gmail message 1a12aabe85e2821d), with Amirul's go (M6 plan Q2): asks whether the permission extends to the interactive web showcase and a public data file of the figures behind the Regions and State reliability charts (2015-2022). Until a yes, the web app leaves them out and the two pages stay images only.
