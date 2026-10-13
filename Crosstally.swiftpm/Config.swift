import Foundation

enum Config {
    /// Where the pre-generated daily files live, e.g. "https://puzzles.example.com/daily"
    /// (an S3 + CloudFront bucket, GitHub Pages, or the Django server's /api/daily).
    /// Leave nil to run fully offline with the bundled puzzles.
    static let puzzleBase: String? = nil

    /// The Django API (accounts, streaks, leaderboards), e.g. "https://api.example.com/api".
    /// Leave nil and the app works as a guest; the account button explains that sign-in is off.
    static let apiBase: String? = nil
}
