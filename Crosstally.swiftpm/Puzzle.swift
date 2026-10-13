import Foundation

struct Pos: Hashable {
    var r: Int
    var c: Int
}

enum Direction {
    case across, down
    var flipped: Direction { self == .across ? .down : .across }
}

/// Letter value: A = 1 ... Z = 26.
func letterValue(_ ch: Character) -> Int {
    guard let a = ch.uppercased().unicodeScalars.first?.value, a >= 65, a <= 90 else { return 0 }
    return Int(a) - 64
}

struct Slot: Identifiable {
    let id: Int
    let dir: Direction
    let number: Int
    let cells: [Pos]
    let answer: String
    let clue: String?          // nil means "number only"
    var total: Int { answer.reduce(0) { $0 + letterValue($1) } }
    var isNumberOnly: Bool { clue == nil }
}

struct Puzzle: Codable, Identifiable {
    let level: Int             // 1 (easiest) ... 4 (hardest)
    let grid: [String]
    let numOnly: [String]
    let clues: [String: String]

    var id: String { grid.joined(separator: "/") }
    var n: Int { grid.count }

    func letter(_ p: Pos) -> Character? {
        guard p.r >= 0, p.c >= 0, p.r < n, p.c < n else { return nil }
        let ch = Array(grid[p.r])[p.c]
        return ch == "#" ? nil : ch
    }

    /// Derive slots (words of 3+ letters) and number them like a normal crossword.
    func makeSlots() -> [Slot] {
        func white(_ r: Int, _ c: Int) -> Bool { letter(Pos(r: r, c: c)) != nil }
        var slots: [Slot] = []
        var next = 1
        var id = 0
        for r in 0..<n {
            for c in 0..<n where white(r, c) {
                let startsAcross = !white(r, c - 1) && white(r, c + 1) && white(r, c + 2)
                let startsDown = !white(r - 1, c) && white(r + 1, c) && white(r + 2, c)
                guard startsAcross || startsDown else { continue }
                let number = next
                next += 1
                for dir in [Direction.across, .down] {
                    guard dir == .across ? startsAcross : startsDown else { continue }
                    var cells: [Pos] = []
                    var p = Pos(r: r, c: c)
                    while white(p.r, p.c) {
                        cells.append(p)
                        p = dir == .across ? Pos(r: p.r, c: p.c + 1) : Pos(r: p.r + 1, c: p.c)
                    }
                    let word = String(cells.compactMap { letter($0) })
                    slots.append(Slot(id: id, dir: dir, number: number, cells: cells,
                                      answer: word, clue: clues[word]))
                    id += 1
                }
            }
        }
        return slots
    }
}

/// One date's four puzzles (levels 1-4), exactly as written by make_daily.py.
struct DailyFile: Codable {
    let date: String
    let puzzles: [Puzzle]
    var isFallback: Bool? = nil
}

enum DateKey {
    private static let formatter: DateFormatter = {
        let f = DateFormatter()
        f.calendar = Calendar(identifier: .gregorian)
        f.locale = Locale(identifier: "en_US_POSIX")
        f.dateFormat = "yyyy-MM-dd"
        return f
    }()

    static func string(_ d: Date) -> String { formatter.string(from: d) }
    static func date(_ s: String) -> Date? { formatter.date(from: s) }
    static var today: String { string(Date()) }

    static func shift(_ s: String, by days: Int) -> String {
        guard let d = date(s), let n = Calendar(identifier: .gregorian).date(byAdding: .day, value: days, to: d) else { return s }
        return string(n)
    }

    static func pretty(_ s: String) -> String {
        guard let d = date(s) else { return s }
        return d.formatted(.dateTime.weekday(.abbreviated).month(.abbreviated).day())
    }

    /// Whole days since 1970 for a date key, used to pick an offline fallback day.
    static func dayNumber(_ s: String) -> Int {
        guard let d = date(s) else { return 0 }
        return Int(d.timeIntervalSince1970 / 86400)
    }
}
