import SwiftUI
import Observation

enum DisplayMode: String { case letters, numbers }

@Observable
final class GameModel {
    let puzzle: Puzzle
    let slots: [Slot]
    var entries: [[Character?]]
    var selected: Pos
    var direction: Direction = .across
    var wrong: Set<Pos> = []
    var mode: DisplayMode = .letters
    var message: String = ""
    var hintsUsed = 0
    var checksUsed = 0
    private var startedAt: Date?
    private var frozenSeconds: Int?

    init(puzzle: Puzzle) {
        self.puzzle = puzzle
        self.slots = puzzle.makeSlots()
        self.entries = Array(repeating: Array(repeating: nil, count: puzzle.n), count: puzzle.n)
        let first = slots.first
        self.selected = first?.cells.first ?? Pos(r: 0, c: 0)
        self.direction = first?.dir ?? .across
    }

    /// Seconds since the first keystroke; stops counting once the puzzle is solved.
    var elapsedSeconds: Int {
        if let f = frozenSeconds { return f }
        guard let t = startedAt else { return 0 }
        return max(1, Int(Date().timeIntervalSince(t)))
    }

    func freezeTimer() { if frozenSeconds == nil { frozenSeconds = elapsedSeconds } }

    // MARK: Lookup

    func isWhite(_ p: Pos) -> Bool { puzzle.letter(p) != nil }

    func slot(at p: Pos, dir: Direction) -> Slot? {
        slots.first { $0.dir == dir && $0.cells.contains(p) }
    }

    var activeSlot: Slot? {
        slot(at: selected, dir: direction) ?? slot(at: selected, dir: direction.flipped)
    }

    func number(at p: Pos) -> Int? {
        slots.first { $0.cells.first == p }?.number
    }

    var across: [Slot] { slots.filter { $0.dir == .across } }
    var down: [Slot] { slots.filter { $0.dir == .down } }

    func filledSum(_ s: Slot) -> Int {
        s.cells.reduce(0) { $0 + (entries[$1.r][$1.c].map(letterValue) ?? 0) }
    }

    func isFilled(_ s: Slot) -> Bool { s.cells.allSatisfy { entries[$0.r][$0.c] != nil } }

    var solved: Bool {
        for r in 0..<puzzle.n {
            for c in 0..<puzzle.n {
                if let want = puzzle.letter(Pos(r: r, c: c)), entries[r][c] != want { return false }
            }
        }
        return true
    }

    var numberAnswersMatching: (done: Int, total: Int) {
        let numSlots = slots.filter { $0.isNumberOnly }
        let ok = numSlots.filter { isFilled($0) && filledSum($0) == $0.total }.count
        return (ok, numSlots.count)
    }

    // MARK: Selection

    func tap(_ p: Pos) {
        guard isWhite(p) else { return }
        if p == selected {
            if slot(at: p, dir: direction.flipped) != nil { direction = direction.flipped }
        } else {
            selected = p
            if slot(at: p, dir: direction) == nil { direction = direction.flipped }
        }
        message = ""
    }

    func select(slot s: Slot) {
        direction = s.dir
        selected = s.cells.first(where: { entries[$0.r][$0.c] == nil }) ?? s.cells[0]
        message = ""
    }

    // MARK: Editing

    func type(_ ch: Character) {
        if startedAt == nil { startedAt = Date() }
        entries[selected.r][selected.c] = ch
        wrong.remove(selected)
        advance()
    }

    func backspace() {
        if entries[selected.r][selected.c] != nil {
            entries[selected.r][selected.c] = nil
            wrong.remove(selected)
        } else {
            retreat()
            entries[selected.r][selected.c] = nil
            wrong.remove(selected)
        }
    }

    private func advance() {
        guard let s = activeSlot, let i = s.cells.firstIndex(of: selected), i + 1 < s.cells.count else { return }
        selected = s.cells[i + 1]
    }

    private func retreat() {
        guard let s = activeSlot, let i = s.cells.firstIndex(of: selected), i > 0 else { return }
        selected = s.cells[i - 1]
    }

    // MARK: Actions

    func check() {
        checksUsed += 1
        wrong = []
        for r in 0..<puzzle.n {
            for c in 0..<puzzle.n {
                let p = Pos(r: r, c: c)
                if let have = entries[r][c], let want = puzzle.letter(p), have != want { wrong.insert(p) }
            }
        }
        message = wrong.isEmpty ? "No wrong letters so far." : "\(wrong.count) letter\(wrong.count == 1 ? " is" : "s are") off."
    }

    func hint() {
        guard let want = puzzle.letter(selected) else { return }
        if startedAt == nil { startedAt = Date() }
        hintsUsed += 1
        entries[selected.r][selected.c] = want
        wrong.remove(selected)
        advance()
    }

    func reset() {
        hintsUsed = 0
        checksUsed = 0
        startedAt = nil
        frozenSeconds = nil
        entries = Array(repeating: Array(repeating: nil, count: puzzle.n), count: puzzle.n)
        wrong = []
        message = ""
    }
}
