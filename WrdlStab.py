# WrdlStab.py
import sys
import re
from collections import Counter

from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QTextCursor
from PyQt6.QtWidgets import (
    QApplication, QWidget, QLabel, QLineEdit, QPushButton, QTextEdit,
    QVBoxLayout, QHBoxLayout, QFileDialog, QMessageBox, QSpinBox,
    QScrollArea
)

def load_word_list(length):
    try:
        from wordfreq import top_n_list
        words = [w.lower() for w in top_n_list("en", 50000) if len(w) == length and w.isalpha()]
        return words
    except Exception:
        return None

def load_wordlist_from_file(path, length):
    words = []
    with open(path, "r", encoding="utf8") as f:
        for line in f:
            w = line.strip().lower()
            if len(w) == length and w.isalpha():
                words.append(w)
    return words

def match_candidates(words, required_letters, pattern, blacklist, yellow_positions):
    req_counter = Counter([c for c in required_letters.lower() if c.isalpha()])
    blacklist_set = set(blacklist.lower())
    pattern_re = '^' + ''.join(
        ('.' if ch in ('_', '.') else re.escape(ch.lower()))
        for ch in pattern
    ) + '$'
    regex = re.compile(pattern_re)
    candidates = []
    for w in words:
        if not regex.match(w):
            continue
        bad = False
        for b in blacklist_set:
            if b in req_counter:
                continue
            if b and b in w:
                bad = True
                break
        if bad:
            continue
        wc = Counter(w)
        ok = True
        for k, v in req_counter.items():
            if wc.get(k, 0) < v:
                ok = False
                break
        if not ok:
            continue
        for pos, letters in yellow_positions.items():
            if pos < 0 or pos >= len(w):
                continue
            if w[pos] in letters:
                bad = True
                break
        if bad:
            continue
        candidates.append(w)
    return candidates

class TileButton(QPushButton):
    STATE_STYLES = {
        1: "background: #9e9e9e; color: white; font-weight: bold;",
        2: "background: #ffeb3b; color: black; font-weight: bold;",
        3: "background: #8bc34a; color: black; font-weight: bold;"
    }
    def __init__(self, index, parent=None):
        super().__init__("", parent)
        self.index = index
        self.letter = ""
        self.state = 1
        self.setFixedSize(34, 34)
        self.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.update_look()
        self.clicked.connect(self.cycle_state)
    def cycle_state(self):
        if not self.letter:
            self.set_state(1, notify=True)
            return
        new_state = 1 + (self.state % 3)
        self.set_state(new_state, notify=True)
    def set_letter(self, ch):
        ch = (ch or "").lower()
        self.letter = ch
        self.setText(self.letter.upper() if self.letter else "")
        if not ch:
            self.set_state(1, notify=False)
        else:
            self.update_look()
    def set_state(self, s, notify=True):
        s = ((s - 1) % 3) + 1
        if self.state == s:
            return
        self.state = s
        self.update_look()
        if notify and hasattr(self, "on_changed"):
            try:
                self.on_changed()
            except Exception:
                pass
    def update_look(self):
        self.setStyleSheet(self.STATE_STYLES[self.state])
        self.setText(self.letter.upper() if self.letter else "")

class RowWidget(QWidget):
    def __init__(self, length, on_row_changed, parent=None):
        super().__init__(parent)
        self.length = length
        self.on_row_changed = on_row_changed
        hl = QHBoxLayout()
        hl.setSpacing(6)
        hl.setContentsMargins(0,0,0,0)
        self.le_input = QLineEdit()
        self.le_input.setMaxLength(length)
        self.le_input.setPlaceholderText("type guess here")
        self.le_input.setFixedWidth(20 * length + 40)
        self.le_input.textChanged.connect(self.on_text_changed)
        self.le_input.returnPressed.connect(self.on_return)
        self.le_input.installEventFilter(self)
        hl.addWidget(self.le_input)
        self.tiles = []
        for i in range(length):
            t = TileButton(i)
            t.on_changed = self.handle_tile_changed
            hl.addWidget(t)
            self.tiles.append(t)
        self.btn_delete = QPushButton("Delete")
        self.btn_delete.setFixedWidth(60)
        self.btn_delete.clicked.connect(self.handle_delete)
        hl.addWidget(self.btn_delete)
        self.setLayout(hl)
    def eventFilter(self, obj, event):
        if obj is self.le_input:
            if event.type() == event.Type.FocusIn:
                if not self.le_input.selectedText():
                    self.le_input.setCursorPosition(len(self.le_input.text()))
            elif event.type() == event.Type.FocusOut:
                self.le_input.setCursorPosition(len(self.le_input.text()))
        return super().eventFilter(obj, event)
    def on_return(self):
        if hasattr(self, "on_enter"):
            self.on_enter()
    def on_text_changed(self, text):
        cleaned = ''.join(ch.lower() for ch in text if ch.isalpha())
        if cleaned != text:
            self.le_input.blockSignals(True)
            self.le_input.setText(cleaned)
            self.le_input.blockSignals(False)
        for i in range(self.length):
            ch = cleaned[i] if i < len(cleaned) else ""
            self.tiles[i].set_letter(ch)
        if self.on_row_changed:
            self.on_row_changed()
    def handle_tile_changed(self):
        for t in self.tiles:
            if not t.letter:
                t.set_state(1, notify=False)
        if self.on_row_changed:
            self.on_row_changed()
    def handle_delete(self):
        if hasattr(self, "on_delete"):
            self.on_delete()
    def get_row_letters(self):
        return ''.join(t.letter for t in self.tiles)
    def get_states(self):
        return [(t.letter, t.state) for t in self.tiles]
    def set_word(self, word):
        word = ''.join(ch.lower() for ch in word if ch.isalpha())[:self.length]
        self.le_input.setText(word)

class WrdlStab(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("WrdlStab")
        self.resize(820, 620)
        top_h = QHBoxLayout()
        top_h.addWidget(QLabel("Word length:"))
        self.spin_length = QSpinBox()
        self.spin_length.setMinimum(1)
        self.spin_length.setMaximum(12)
        self.spin_length.setValue(5)
        self.spin_length.valueChanged.connect(self.on_length_changed)
        top_h.addWidget(self.spin_length)
        self.btn_load_file = QPushButton("Load wordlist file")
        self.btn_load_file.clicked.connect(self.load_file)
        top_h.addWidget(self.btn_load_file)
        self.btn_try_auto = QPushButton("Reload builtin (wordfreq)")
        self.btn_try_auto.clicked.connect(self.try_auto_load)
        top_h.addWidget(self.btn_try_auto)
        top_h.addStretch()
        self.rows_container = QWidget()
        self.rows_layout = QVBoxLayout()
        self.rows_layout.setContentsMargins(6,6,6,6)
        self.rows_layout.setSpacing(6)
        self.rows_container.setLayout(self.rows_layout)
        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setWidget(self.rows_container)
        self.scroll.setFixedHeight(240)
        rows_btn_h = QHBoxLayout()
        self.btn_add_row = QPushButton("Add row")
        self.btn_add_row.clicked.connect(self.add_row)
        rows_btn_h.addWidget(self.btn_add_row)
        self.btn_add_row_last = QPushButton("Add row (and focus)")
        self.btn_add_row_last.clicked.connect(lambda: self.add_row(focus=True))
        rows_btn_h.addWidget(self.btn_add_row_last)
        rows_btn_h.addStretch()
        self.btn_clear_rows = QPushButton("Clear all rows")
        self.btn_clear_rows.clicked.connect(self.clear_rows)
        rows_btn_h.addWidget(self.btn_clear_rows)
        find_h = QHBoxLayout()
        self.btn_find = QPushButton("Find possibilities (from rows)")
        self.btn_find.clicked.connect(self.on_find)
        find_h.addWidget(self.btn_find)
        self.btn_copy = QPushButton("Copy first candidate")
        self.btn_copy.clicked.connect(self.copy_first)
        find_h.addWidget(self.btn_copy)
        find_h.addStretch()
        self.results = QTextEdit()
        self.results.setReadOnly(True)
        self.results.setPlaceholderText("Matching words will appear here...")
        main = QVBoxLayout()
        main.addLayout(top_h)
        main.addWidget(QLabel("Rows (type a guess then click tiles to color):"))
        main.addWidget(self.scroll)
        main.addLayout(rows_btn_h)
        main.addLayout(find_h)
        main.addWidget(QLabel("Results:"))
        main.addWidget(self.results)
        self.setLayout(main)
        self.words = []
        self.rows = []
        self.try_auto_load()
        self.add_row()
    def on_length_changed(self, newlen):
        old_words = [r.get_row_letters() for r in self.rows]
        for r in self.rows:
            r.setParent(None)
        self.rows = []
        for w in old_words:
            self.add_row(word=w[:newlen])
        if not self.rows:
            self.add_row()
        self.try_auto_load()
        QTimer.singleShot(0, lambda: self.scroll.verticalScrollBar().setValue(self.scroll.verticalScrollBar().maximum()))
    def add_row(self, word="", focus=False):
        length = self.spin_length.value()
        row = RowWidget(length, on_row_changed=self.on_row_changed)
        def do_delete(r=row):
            self.rows_layout.removeWidget(r)
            r.setParent(None)
            self.rows.remove(r)
            self.on_row_changed()
        row.on_delete = do_delete
        row.on_enter = lambda: self.add_row(focus=True)
        self.rows_layout.addWidget(row)
        self.rows.append(row)
        if word:
            row.set_word(word)
        if focus:
            row.le_input.setFocus()
        QTimer.singleShot(0, lambda: self.scroll.verticalScrollBar().setValue(self.scroll.verticalScrollBar().maximum()))
        self.on_row_changed()
    def clear_rows(self):
        for r in list(self.rows):
            r.setParent(None)
        self.rows = []
        self.add_row()
        self.on_row_changed()
    def on_row_changed(self):
        pass
    def try_auto_load(self):
        length = self.spin_length.value()
        words = load_word_list(length)
        if words:
            self.words = words
        else:
            self.words = []
    def load_file(self):
        path, _ = QFileDialog.getOpenFileName(self, "Open wordlist file", "", "Text files (*.txt);;All files (*)")
        if not path:
            return
        try:
            length = self.spin_length.value()
            self.words = load_wordlist_from_file(path, length)
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to load file:\n{e}")
    def gather_constraints(self):
        length = self.spin_length.value()
        pattern = ['.' for _ in range(length)]
        greens_by_pos = {}
        yellow_positions = {}
        yellow_seen = []
        grey_set = set()
        for row in self.rows:
            states = row.get_states()
            for i, (letter, state) in enumerate(states):
                if not letter:
                    continue
                if state == 3:
                    greens_by_pos.setdefault(i, set()).add(letter)
                elif state == 2:
                    yellow_positions.setdefault(i, set()).add(letter)
                    if letter not in yellow_seen:
                        yellow_seen.append(letter)
                elif state == 1:
                    grey_set.add(letter)
        for pos, letters in greens_by_pos.items():
            if len(letters) > 1:
                all_letters = [chr(c) for c in range(ord('a'), ord('z')+1)]
                blacklist_set = set(all_letters)
                pattern_str = ''.join(pattern)
                req_letters = ""
                blacklist = ''.join(sorted(blacklist_set))
                return req_letters, pattern_str, blacklist, yellow_positions
        required_ordered = []
        for pos in range(length):
            if pos in greens_by_pos:
                letter = next(iter(greens_by_pos[pos]))
                pattern[pos] = letter
                if letter not in required_ordered:
                    required_ordered.append(letter)
        for letter in yellow_seen:
            if letter not in required_ordered:
                required_ordered.append(letter)
        req_letters = ''.join(required_ordered)
        blacklist_set = set(grey_set)
        for letter in list(blacklist_set):
            if letter in req_letters:
                blacklist_set.discard(letter)
        pattern_str = ''.join(pattern)
        blacklist = ''.join(sorted(blacklist_set))
        return req_letters, pattern_str, blacklist, yellow_positions
    def on_find(self):
        length = self.spin_length.value()
        if not self.words:
            self.try_auto_load()
            if not self.words:
                QMessageBox.warning(self, "No words loaded", "Please load a wordlist (wordfreq or a local file).")
                return
        required, pattern, blacklist, yellow_positions = self.gather_constraints()
        if len(pattern) != length:
            QMessageBox.warning(self, "Pattern length mismatch", f"Pattern ({len(pattern)}) must be same length as word length ({length}).")
            return
        candidates = match_candidates(
            self.words,
            required,
            pattern,
            blacklist,
            yellow_positions
        )
        if not candidates:
            self.results.setPlainText("No matches.")
            self.results.moveCursor(QTextCursor.MoveOperation.Start)
            return
        try:
            from wordfreq import zipf_frequency
            candidates = sorted(candidates, key=lambda w: -zipf_frequency(w, "en"))
        except Exception:
            candidates = sorted(candidates)
        out = []
        out.append(f"{len(candidates)} candidate(s):\n")
        MAX_SHOW = 500
        for i, w in enumerate(candidates):
            if i >= MAX_SHOW:
                out.append(f"... and {len(candidates)-MAX_SHOW} more")
                break
            out.append(w)
        text = "\n".join(out)
        self.results.setPlainText(text)
        self.results.moveCursor(QTextCursor.MoveOperation.Start)
        self.results.ensureCursorVisible()
    def copy_first(self):
        txt = self.results.toPlainText().strip().splitlines()
        if not txt:
            return
        first = None
        for line in txt:
            line = line.strip()
            if not line:
                continue
            if re.match(r"^\d+\s+candidate", line):
                continue
            first = line
            break
        if first:
            clipboard = QApplication.clipboard()
            clipboard.setText(first)
        else:
            QMessageBox.information(self, "No candidate", "No candidate to copy.")

if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = WrdlStab()
    window.show()
    sys.exit(app.exec())
