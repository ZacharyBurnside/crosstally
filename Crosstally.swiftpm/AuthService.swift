import Foundation
import AuthenticationServices
import Observation

struct ServerStats: Decodable {
    let solved: Int
    let daysPlayed: Int
    let currentStreak: Int
    let bestStreak: Int
}

struct PendingResult: Codable, Equatable {
    let date: String
    let level: Int
    let seconds: Int
    let hints: Int
    let checks: Int
}

/// Optional account: the game works fully as a guest. Signing in (Sign in with Apple) syncs results,
/// streaks and leaderboard entries through the Django API. Results made while signed out or offline
/// wait in a local queue and are sent later.
@MainActor @Observable
final class AuthService {
    private(set) var token: String? = Keychain.read("api-token")
    var stats: ServerStats?
    var displayName = ""
    var message: String?
    private var pending: [PendingResult] = []

    var isConfigured: Bool { Config.apiBase != nil }
    var isSignedIn: Bool { token != nil }

    init() {
        if let data = UserDefaults.standard.data(forKey: "pendingResults"),
           let list = try? JSONDecoder().decode([PendingResult].self, from: data) { pending = list }
    }

    // MARK: Sign in

    func handle(_ result: Result<ASAuthorization, Error>) async {
        guard isConfigured else { message = "Accounts are not set up yet (Config.apiBase)."; return }
        switch result {
        case .failure(let error):
            message = "Sign in failed: \(error.localizedDescription)"
        case .success(let auth):
            guard let cred = auth.credential as? ASAuthorizationAppleIDCredential,
                  let tokenData = cred.identityToken, let identity = String(data: tokenData, encoding: .utf8) else {
                message = "Apple did not return a token."
                return
            }
            do {
                let data = try await call("auth/apple", method: "POST", body: ["identity_token": identity], auth: false)
                if let obj = try JSONSerialization.jsonObject(with: data) as? [String: Any], let t = obj["token"] as? String {
                    token = t
                    Keychain.write("api-token", t)
                    message = nil
                    await refresh()
                    await flush()
                }
            } catch {
                message = "Could not sign in: \(error.localizedDescription)"
            }
        }
    }

    func signOut() {
        token = nil
        stats = nil
        Keychain.write("api-token", nil)
    }

    func deleteAccount() async {
        do {
            _ = try await call("me", method: "DELETE")
            signOut()
            pending = []
            savePending()
        } catch {
            message = "Could not delete the account: \(error.localizedDescription)"
        }
    }

    func saveName(_ name: String) async {
        _ = try? await call("me", method: "PATCH", body: ["display_name": name])
    }

    // MARK: Results

    func record(_ r: PendingResult) async {
        if !pending.contains(r) { pending.append(r) }
        savePending()
        await flush()
    }

    func flush() async {
        guard isSignedIn, isConfigured else { return }
        for r in pending {
            do {
                _ = try await call("completions", method: "POST", body: [
                    "date": r.date, "level": r.level, "seconds": r.seconds, "hints": r.hints, "checks": r.checks])
                pending.removeAll { $0 == r }
            } catch { break }          // offline or server error: keep the rest queued
        }
        savePending()
        await refresh()
    }

    func refresh() async {
        guard isSignedIn, isConfigured else { return }
        guard let data = try? await call("me"),
              let obj = try? JSONSerialization.jsonObject(with: data) as? [String: Any] else { return }
        displayName = obj["display_name"] as? String ?? ""
        if let s = obj["stats"], let sd = try? JSONSerialization.data(withJSONObject: s) {
            let dec = JSONDecoder()
            dec.keyDecodingStrategy = .convertFromSnakeCase
            stats = try? dec.decode(ServerStats.self, from: sd)
        }
    }

    // MARK: HTTP

    private func savePending() {
        if let d = try? JSONEncoder().encode(pending) { UserDefaults.standard.set(d, forKey: "pendingResults") }
    }

    private struct APIError: LocalizedError {
        let status: Int
        var errorDescription: String? { "server returned \(status)" }
    }

    private func call(_ path: String, method: String = "GET", body: [String: Any]? = nil, auth: Bool = true) async throws -> Data {
        guard let base = Config.apiBase, let url = URL(string: "\(base)/\(path)") else { throw APIError(status: 0) }
        var req = URLRequest(url: url)
        req.httpMethod = method
        req.timeoutInterval = 15
        if let body {
            req.httpBody = try JSONSerialization.data(withJSONObject: body)
            req.setValue("application/json", forHTTPHeaderField: "Content-Type")
        }
        if auth, let token { req.setValue("Bearer \(token)", forHTTPHeaderField: "Authorization") }
        let (data, resp) = try await URLSession.shared.data(for: req)
        let code = (resp as? HTTPURLResponse)?.statusCode ?? 0
        if code == 401 && auth { signOut() }                       // expired or revoked token
        guard (200..<300).contains(code) else { throw APIError(status: code) }
        return data
    }
}
