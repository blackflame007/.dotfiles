// Bromigos start page for LibreWolf. Linked as user.js into the LibreWolf profile
// (~/.librewolf/<profile>/user.js); LibreWolf re-applies it on every start.
// Home button and new windows open the start page. Session restore is left as it is.
// New tabs cannot be set from prefs in Firefox-based browsers: see AGENTS.md
// ("Start page") for the one-time extension step.
user_pref("browser.startup.homepage", "file:///home/blackflame/.config/bromigos/startpage/index.html");
