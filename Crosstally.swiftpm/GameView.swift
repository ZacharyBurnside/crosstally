import SwiftUI

struct GameView: View {
    @Bindable var model: GameModel
    var onSolved: (_ seconds: Int, _ hints: Int, _ checks: Int) -> Void
    @State private var showClues = false

    var body: some View {
        VStack(spacing: 8) {
            caption
            GridView(model: model)
            status
            activeBar
            KeyboardView(model: model)
            actions
        }
        .sheet(isPresented: $showClues) { ClueListView(model: model) }
        .onChange(of: model.solved) { _, solved in
            if solved {
                model.freezeTimer()
                onSolved(max(1, model.elapsedSeconds), model.hintsUsed, model.checksUsed)
                UINotificationFeedbackGenerator().notificationOccurred(.success)
            }
        }
    }

    private var caption: some View {
        HStack {
            TimelineView(.periodic(from: .now, by: 1)) { _ in
                let s = model.elapsedSeconds
                Text(String(format: "%d:%02d", s / 60, s % 60))
                    .font(.system(.footnote, design: .monospaced).weight(.semibold))
                    .foregroundStyle(.secondary)
            }
            Spacer()
            Picker("Display", selection: $model.mode) {
                Text("Letters").tag(DisplayMode.letters)
                Text("Numbers").tag(DisplayMode.numbers)
            }
            .pickerStyle(.segmented)
            .frame(maxWidth: 190)
        }
    }

    private var status: some View {
        let m = model.numberAnswersMatching
        let text: String
        if model.solved { text = "Solved! 🎉" }
        else if !model.message.isEmpty { text = model.message }
        else { text = "Number answers matching their total: \(m.done) of \(m.total)" }
        return Text(text)
            .font(.footnote.weight(model.solved ? .bold : .regular))
            .foregroundStyle(model.solved ? Color.green : Color.secondary)
            .frame(maxWidth: .infinity, alignment: .leading)
    }

    private var activeBar: some View {
        Button { showClues = true } label: {
            HStack {
                if let s = model.activeSlot {
                    Text("\(s.number) \(s.dir == .across ? "Across" : "Down")")
                        .font(.system(.footnote, design: .monospaced).weight(.bold))
                        .foregroundStyle(Color.accentColor)
                    Text(s.clue ?? "Number only")
                        .font(.subheadline).lineLimit(1)
                    Spacer()
                    if s.isNumberOnly {
                        Text("\(model.filledSum(s)) of \(s.total)")
                            .font(.system(.footnote, design: .monospaced))
                            .foregroundStyle(.secondary)
                    } else {
                        Text("(\(s.cells.count))").font(.footnote).foregroundStyle(.secondary)
                    }
                }
            }
            .padding(.horizontal, 12).padding(.vertical, 10)
            .background(Color(.secondarySystemBackground), in: RoundedRectangle(cornerRadius: 10))
        }
        .buttonStyle(.plain)
    }

    private var actions: some View {
        HStack(spacing: 8) {
            actionButton("Check", prominent: true) { model.check() }
            actionButton("Hint") { model.hint() }
            actionButton("Clues") { showClues = true }
            actionButton("Reset") { model.reset() }
        }
    }

    private func actionButton(_ title: String, prominent: Bool = false, _ action: @escaping () -> Void) -> some View {
        Button(action: action) {
            Text(title).font(.subheadline.weight(.semibold)).frame(maxWidth: .infinity).padding(.vertical, 10)
                .background(prominent ? Color.primary : Color(.secondarySystemBackground),
                            in: RoundedRectangle(cornerRadius: 10))
                .foregroundStyle(prominent ? Color(.systemBackground) : Color.primary)
        }
    }
}

struct GridView: View {
    var model: GameModel

    var body: some View {
        GeometryReader { geo in
            let n = model.puzzle.n
            let cell = min(72, floor(geo.size.width / CGFloat(n)))
            VStack(spacing: 0) {
                ForEach(0..<n, id: \.self) { r in
                    HStack(spacing: 0) {
                        ForEach(0..<n, id: \.self) { c in
                            CellView(model: model, pos: Pos(r: r, c: c), size: cell)
                        }
                    }
                }
            }
            .overlay(Rectangle().stroke(Color.primary, lineWidth: 2))
            .frame(width: cell * CGFloat(n), height: cell * CGFloat(n))
            .frame(maxWidth: .infinity)
        }
        .aspectRatio(1, contentMode: .fit)
    }
}

struct CellView: View {
    var model: GameModel
    let pos: Pos
    let size: CGFloat

    var body: some View {
        let white = model.isWhite(pos)
        let isSelected = pos == model.selected
        let inWord = model.activeSlot?.cells.contains(pos) ?? false
        let isWrong = model.wrong.contains(pos)

        ZStack {
            Rectangle().fill(background(white: white, selected: isSelected, inWord: inWord, wrong: isWrong))
            if white {
                if let n = model.number(at: pos) {
                    Text("\(n)").font(.system(size: 10, weight: .bold, design: .monospaced))
                        .foregroundStyle(.secondary)
                        .frame(maxWidth: .infinity, maxHeight: .infinity, alignment: .topLeading)
                        .padding(3)
                }
                if let ch = model.entries[pos.r][pos.c] {
                    if model.mode == .letters {
                        Text(String(ch)).font(.system(size: size * 0.5, weight: .bold, design: .rounded))
                    } else {
                        Text("\(letterValue(ch))").font(.system(size: size * 0.4, weight: .bold, design: .monospaced))
                    }
                }
            }
        }
        .frame(width: size, height: size)
        .overlay(Rectangle().stroke(Color(.separator), lineWidth: 0.5))
        .contentShape(Rectangle())
        .onTapGesture { model.tap(pos) }
    }

    private func background(white: Bool, selected: Bool, inWord: Bool, wrong: Bool) -> Color {
        if !white { return Color(.label) }
        if wrong { return Color.red.opacity(0.3) }
        if selected { return Color.accentColor.opacity(0.45) }
        if inWord { return Color.accentColor.opacity(0.15) }
        return Color(.systemBackground)
    }
}

struct KeyboardView: View {
    var model: GameModel
    private let rows = ["QWERTYUIOP", "ASDFGHJKL", "ZXCVBNM"]

    var body: some View {
        VStack(spacing: 6) {
            ForEach(rows, id: \.self) { row in
                HStack(spacing: 5) {
                    ForEach(Array(row), id: \.self) { ch in
                        Button { model.type(ch) } label: {
                            VStack(spacing: 0) {
                                Text(String(ch)).font(.system(size: 18, weight: .semibold, design: .rounded))
                                Text("\(letterValue(ch))")
                                    .font(.system(size: 9, design: .monospaced)).foregroundStyle(.secondary)
                            }
                            .frame(maxWidth: .infinity).frame(height: 42)
                            .background(Color(.secondarySystemBackground), in: RoundedRectangle(cornerRadius: 7))
                            .foregroundStyle(.primary)
                        }
                    }
                    if row == rows.last {
                        Button { model.backspace() } label: {
                            Image(systemName: "delete.left")
                                .frame(width: 46, height: 42)
                                .background(Color(.tertiarySystemBackground), in: RoundedRectangle(cornerRadius: 7))
                                .foregroundStyle(.primary)
                        }
                    }
                }
            }
        }
    }
}

struct ClueListView: View {
    var model: GameModel
    @Environment(\.dismiss) private var dismiss

    var body: some View {
        NavigationStack {
            List {
                section("Across", model.across)
                section("Down", model.down)
            }
            .navigationTitle("Clues")
            .navigationBarTitleDisplayMode(.inline)
            .toolbar { ToolbarItem(placement: .confirmationAction) { Button("Done") { dismiss() } } }
        }
        .presentationDetents([.medium, .large])
    }

    private func section(_ title: String, _ slots: [Slot]) -> some View {
        Section(title) {
            ForEach(slots) { s in
                Button {
                    model.select(slot: s)
                    dismiss()
                } label: {
                    HStack(alignment: .firstTextBaseline) {
                        Text("\(s.number)").font(.system(.footnote, design: .monospaced).weight(.bold))
                            .foregroundStyle(Color.accentColor).frame(width: 22, alignment: .leading)
                        if let clue = s.clue {
                            Text("\(clue) (\(s.cells.count))")
                        } else {
                            Text("Number only (\(s.cells.count))").foregroundStyle(.secondary)
                            Spacer()
                            let sum = model.filledSum(s)
                            let ok = model.isFilled(s) && sum == s.total
                            Text("\(s.total)")
                                .font(.system(.footnote, design: .monospaced).weight(.bold))
                                .padding(.horizontal, 6).padding(.vertical, 2)
                                .background(ok ? Color.green.opacity(0.25) : Color.accentColor.opacity(0.2),
                                            in: RoundedRectangle(cornerRadius: 5))
                        }
                    }
                    .foregroundStyle(.primary)
                }
            }
        }
    }
}
