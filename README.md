# Job Application Control Center — automated Job Hunter

The original Strategy tab is preserved, alongside the existing Overview, Applications, ATS and AI Job Hunter tabs.

## Deploy (GitHub Pages)
1. Create a GitHub repository (public repository is simplest for GitHub Pages) and upload the contents of this folder, including `.github/workflows/job-hunter.yml`.
2. In **Settings → Pages**, choose **Deploy from a branch**, `main`, `/ (root)`, and save.
3. In **Actions**, enable workflows and run **Daily AI Job Hunter** once using **Run workflow**.
4. Visit the Pages URL. The AI Job Hunter tab reads `data/jobs.json` automatically and refreshes every 15 minutes while open. The workflow runs daily at 07:00 UTC (08:00 in winter / 09:00 in summer in Munich).

## What is and is not automatic
- Automated: public feed collection from Remotive and Arbeitnow, basic title/skills/language/location filtering, duplicate detection, publishing the JSON feed, automatic loading in the hosted dashboard.
- Not automated: direct integration with the ChatGPT scheduled Task, private LinkedIn/XING searches, AI/LLM semantic scoring, salary verification, and cross-device sync of the Applications tab (which still uses browser localStorage).
- Matches are **heuristic estimates**, not verified ATS scores. Review actual job requirements before applying.
- If no public source is reachable or no new matches are found, the feed can be empty or contain older retained entries.
- To keep job search data private, use a private backend/database and authentication instead of public GitHub Pages. Public GitHub Pages exposes the JSON feed.

## Security
Do not upload private CVs, personal application records, or credentials to a public repository. The hosted page's Applications tab still stores entries locally in your browser.
