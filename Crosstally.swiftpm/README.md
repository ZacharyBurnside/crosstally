# Crosstally (iPhone app)

Open this folder in Xcode 15+ (File > Open) and press Run on an iPhone simulator.
If Xcode asks for a signing team, pick your Personal Team (Xcode > Settings > Accounts) or set `teamIdentifier`
in Package.swift.

## Files
- `Puzzle.swift`        models, slot numbering, date helpers
- `GameModel.swift`     game state: selection, typing, check/hint/reset, timer
- `GameView.swift`      grid, keyboard, clue sheet
- `RootView.swift`      date stepper, level 1-4 picker, account button
- `DailyService.swift`  loads a day: memory -> disk cache -> network -> bundled fallback
- `AuthService.swift`   optional Sign in with Apple + results queue + stats
- `AccountView.swift`   profile, stats, sign out, delete account
- `Config.swift`        set `puzzleBase` and `apiBase` to go online (both nil = fully offline)
- `BundledDays.swift`   7 generated days used as the offline fallback

## Going online
1. Publish the `daily/` folder (GitHub Pages, S3 + CloudFront, or the Django server) and set
   `Config.puzzleBase`, e.g. "https://puzzles.example.com/daily".
2. Deploy `backend/` and set `Config.apiBase`, e.g. "https://api.example.com/api".
3. Sign in with Apple needs the capability in a real Xcode project (paid developer team). The app works as a
   guest without it; the button stays disabled until `apiBase` is set.
