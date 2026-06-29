import SwiftUI

/// Minimal input line — text field + coral 🎤 + blue ➤.
struct InputLine: View {
    @Binding var text: String
    @FocusState.Binding var isFocused: Bool
    let isEnabled: Bool
    let unavailableReason: String?
    var onSend: () -> Void

    var body: some View {
        VStack(alignment: .leading, spacing: 6) {
            if let unavailableReason, !isEnabled {
                Text(unavailableReason)
                    .font(Paper.tinyFont)
                    .foregroundStyle(Paper.faint)
            }

            HStack(spacing: 12) {
                // Text input (no border, no box)
                TextField(L10n.str("说点什么...", en: "Type something..."), text: $text, axis: .vertical)
                    .textFieldStyle(.plain)
                    .font(Paper.inputFont)
                    .foregroundStyle(isEnabled ? Paper.herText : Paper.faint)
                    .lineLimit(1...4)
                    .focused($isFocused)
                    .disabled(!isEnabled)
                    .onSubmit {
                        if isEnabled && !NSEvent.modifierFlags.contains(.shift) {
                            onSend()
                        }
                    }

                // Coral microphone
                Button(action: {}) {
                    Image(systemName: "mic")
                        .font(.system(size: 16))
                        .foregroundStyle(isEnabled ? Paper.coral : Paper.faint)
                }
                .buttonStyle(.plain)
                .disabled(!isEnabled)

                // Blue send arrow
                Button(action: onSend) {
                    Image(systemName: "arrowtriangle.right.fill")
                        .font(.system(size: 16))
                        .foregroundStyle(
                            text.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty || !isEnabled
                            ? Paper.faint
                            : Paper.ink
                        )
                }
                .buttonStyle(.plain)
                .disabled(!isEnabled || text.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty)
            }
        }
        .padding(.horizontal, Paper.hPadding)
        .padding(.top, 14)
        .padding(.bottom, 16)
    }
}
