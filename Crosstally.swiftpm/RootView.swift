import SwiftUI

struct RootView: View {
    @State private var daily = DailyService()
    @State private var auth = AuthService()
    @State private var date = DateKey.today
    @State private var level = 1
    @State private var file: DailyFile?
    @State private var loading = true
    @State private var cache = ModelCache()
    @State private var showAccount = false
    @AppStorage("solvedKeys") private var solvedRaw = ""

    private var solvedSet: Set<String> { Set(solvedRaw.split(separator: ",").map(String.init)) }
    private func key(_ d: String, _ l: Int) -> String { "\(d)#\(l)" }

    var body: some View {
        VStack(spacing: 8) {
            header
            dateStepper
            levelPicker
            content
        }
        .padding(.horizontal, 16)
        .padding(.top, 4)
        .task(id: date) { await loadDay() }
        .sheet(isPresented: $showAccount) { AccountView(auth: auth) }
        .task { await auth.flush() }
    }

    @ViewBuilder private var content: some View {
        if loading {
            ProgressView().frame(maxHeight: .infinity)
        } else if let f = file, let p = f.puzzles.first(where: { $0.level == level }) {
            GameView(model: cache.model(date: date, puzzle: p)) { seconds, hints, checks in
                markSolved(date: date, level: level, seconds: seconds, hints: hints, checks: checks)
            }
            .id(key(date, level))
            if f.isFallback == true {
                Text("Offline puzzle set").font(.caption2).foregroundStyle(.secondary)
            }
        } else {
            Text("No puzzle available for this day.").foregroundStyle(.secondary).frame(maxHeight: .infinity)
        }
    }

    private func loadDay() async {
        loading = true
        file = await daily.load(date)
        loading = false
    }

    private func markSolved(date: String, level: Int, seconds: Int, hints: Int, checks: Int) {
        var s = solvedSet
        s.insert(key(date, level))
        solvedRaw = s.sorted().joined(separator: ",")
        Task { await auth.record(PendingResult(date: date, level: level, seconds: seconds, hints: hints, checks: checks)) }
    }

    private var header: some View {
        HStack {
            Text("Crosstally").font(.system(size: 28, weight: .bold, design: .rounded))
            Spacer()
            if let s = auth.stats, s.currentStreak > 0 {
                Label("\(s.currentStreak)", systemImage: "flame.fill")
                    .font(.subheadline.weight(.semibold)).foregroundStyle(.orange)
            }
            Button { showAccount = true } label: {
                Image(systemName: auth.isSignedIn ? "person.crop.circle.fill" : "person.crop.circle")
                    .font(.title2)
            }
        }
    }

    private var dateStepper: some View {
        HStack {
            Button { date = DateKey.shift(date, by: -1) } label: { Image(systemName: "chevron.left") }
            Spacer()
            Text(date == DateKey.today ? "Today · \(DateKey.pretty(date))" : DateKey.pretty(date))
                .font(.subheadline.weight(.semibold))
            Spacer()
            Button { date = DateKey.shift(date, by: 1) } label: { Image(systemName: "chevron.right") }
                .disabled(date >= DateKey.today)
        }
    }

    private var levelPicker: some View {
        HStack(spacing: 6) {
            ForEach(1...4, id: \.self) { l in
                let done = solvedSet.contains(key(date, l))
                Button { level = l } label: {
                    VStack(spacing: 0) {
                        Text("\(l)" + (done ? " ✓" : ""))
                            .font(.system(.subheadline, design: .monospaced).weight(.bold))
                        Text(["Easy", "Medium", "Hard", "Expert"][l - 1]).font(.caption2)
                    }
                    .frame(maxWidth: .infinity).padding(.vertical, 6)
                    .background(l == level ? Color.accentColor.opacity(0.2) : Color(.secondarySystemBackground),
                                in: RoundedRectangle(cornerRadius: 8))
                    .overlay(RoundedRectangle(cornerRadius: 8)
                        .stroke(l == level ? Color.accentColor : Color(.separator), lineWidth: 1.5))
                }
                .buttonStyle(.plain)
            }
        }
    }
}

/// Keeps each puzzle's in-progress state while you switch between levels and days.
final class ModelCache {
    private var models: [String: GameModel] = [:]
    func model(date: String, puzzle: Puzzle) -> GameModel {
        let k = "\(date)#\(puzzle.level)"
        if let m = models[k] { return m }
        let m = GameModel(puzzle: puzzle)
        models[k] = m
        return m
    }
}
