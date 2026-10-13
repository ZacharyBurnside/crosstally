import Foundation
import Observation

/// Loads a day's four puzzles: memory -> disk cache -> network -> bundled fallback.
@MainActor @Observable
final class DailyService {
    private var memory: [String: DailyFile] = [:]

    func load(_ date: String) async -> DailyFile? {
        if let f = memory[date] { return f }
        if let f = readDisk(date) { memory[date] = f; return f }
        if let base = Config.puzzleBase, let url = URL(string: "\(base)/\(date).json") {
            do {
                let (data, resp) = try await URLSession.shared.data(from: url)
                if (resp as? HTTPURLResponse)?.statusCode == 200,
                   let f = try? JSONDecoder().decode(DailyFile.self, from: data), f.puzzles.count == 4 {
                    writeDisk(data, date)
                    memory[date] = f
                    return f
                }
            } catch { /* offline: fall through to the bundled set */ }
        }
        return fallback(for: date)
    }

    // Bundled days repeat in a cycle; only used when a date can't be fetched.
    private func fallback(for date: String) -> DailyFile? {
        guard let data = BundledDays.json.data(using: .utf8),
              let days = try? JSONDecoder().decode([DailyFile].self, from: data), !days.isEmpty else { return nil }
        var f = days[DateKey.dayNumber(date) % days.count]
        f = DailyFile(date: date, puzzles: f.puzzles, isFallback: true)
        return f
    }

    private var folder: URL? {
        guard let base = try? FileManager.default.url(for: .applicationSupportDirectory, in: .userDomainMask,
                                                      appropriateFor: nil, create: true) else { return nil }
        let dir = base.appendingPathComponent("daily", isDirectory: true)
        try? FileManager.default.createDirectory(at: dir, withIntermediateDirectories: true)
        return dir
    }

    private func readDisk(_ date: String) -> DailyFile? {
        guard let url = folder?.appendingPathComponent(date + ".json"),
              let data = try? Data(contentsOf: url) else { return nil }
        return try? JSONDecoder().decode(DailyFile.self, from: data)
    }

    private func writeDisk(_ data: Data, _ date: String) {
        guard let url = folder?.appendingPathComponent(date + ".json") else { return }
        try? data.write(to: url, options: .atomic)
    }
}
