import SwiftUI
import AuthenticationServices

struct AccountView: View {
    var auth: AuthService
    @Environment(\.dismiss) private var dismiss
    @State private var name = ""
    @State private var confirmDelete = false

    var body: some View {
        NavigationStack {
            Form {
                if auth.isSignedIn {
                    Section("Profile") {
                        TextField("Display name (shown on leaderboards)", text: $name)
                            .onSubmit { Task { await auth.saveName(name) } }
                        Text("Leave blank to stay off the leaderboards.").font(.caption).foregroundStyle(.secondary)
                    }
                    if let s = auth.stats {
                        Section("Your stats") {
                            row("Current streak", "\(s.currentStreak) days")
                            row("Best streak", "\(s.bestStreak) days")
                            row("Puzzles solved", "\(s.solved)")
                            row("Days played", "\(s.daysPlayed)")
                        }
                    }
                    Section {
                        Button("Sign out") { auth.signOut(); dismiss() }
                        Button("Delete account", role: .destructive) { confirmDelete = true }
                    }
                } else {
                    Section {
                        Text("Playing as a guest. Sign in to keep your streak across devices and appear on leaderboards.")
                            .font(.subheadline)
                        SignInWithAppleButton(.signIn, onRequest: { $0.requestedScopes = [.email] },
                                              onCompletion: { r in Task { await auth.handle(r) } })
                            .frame(height: 44)
                            .disabled(!auth.isConfigured)
                        if !auth.isConfigured {
                            Text("Accounts are off until Config.apiBase points at your server.")
                                .font(.caption).foregroundStyle(.secondary)
                        }
                    }
                }
                if let m = auth.message {
                    Section { Text(m).font(.footnote).foregroundStyle(.red) }
                }
            }
            .navigationTitle("Account")
            .navigationBarTitleDisplayMode(.inline)
            .toolbar { ToolbarItem(placement: .confirmationAction) { Button("Done") { dismiss() } } }
            .onAppear { name = auth.displayName }
            .task { await auth.refresh(); name = auth.displayName }
            .confirmationDialog("Delete your account and all synced results?", isPresented: $confirmDelete,
                                titleVisibility: .visible) {
                Button("Delete account", role: .destructive) { Task { await auth.deleteAccount(); dismiss() } }
            }
        }
    }

    private func row(_ k: String, _ v: String) -> some View {
        HStack { Text(k); Spacer(); Text(v).foregroundStyle(.secondary) }
    }
}
