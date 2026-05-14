import SwiftUI
import UIKit

struct ContentView: View {
    @StateObject private var viewModel = ChatViewModel()

    var body: some View {
        VStack(spacing: 0) {
            header
            messages
        }
        .safeAreaInset(edge: .bottom) {
            inputBar
        }
        .frame(maxWidth: .infinity, maxHeight: .infinity, alignment: .top)
        .background(Color(.systemBackground))
        .overlay(alignment: .bottomLeading) {
            Text(viewModel.lastToolCalled)
                .font(.caption2)
                .foregroundColor(.clear)
                .accessibilityIdentifier("last_tool_called")
                .padding(.leading, 1)
                .padding(.bottom, 1)
                .allowsHitTesting(false)
        }
        .overlay(alignment: .bottomLeading) {
            Text(viewModel.capturedAudioPath)
                .font(.caption2)
                .foregroundColor(.clear)
                .accessibilityIdentifier("captured_audio_path")
                .padding(.leading, 1)
                .padding(.bottom, 1)
                .allowsHitTesting(false)
        }
        .onAppear { viewModel.setup() }
    }

    private var header: some View {
        HStack {
            Text("VoiceText Demo")
                .font(.headline)
            Spacer()
            Circle()
                .fill(viewModel.isConnected ? Color.green : Color.red)
                .frame(width: 10, height: 10)
                .accessibilityIdentifier("connection_indicator")
        }
        .padding()
        .background(Color(.systemBackground))
        .overlay(Rectangle().frame(height: 0.5).foregroundColor(Color(.separator)), alignment: .bottom)
    }

    private var messages: some View {
        ScrollViewReader { proxy in
            ScrollView {
                LazyVStack(alignment: .leading, spacing: 8) {
                    ForEach(viewModel.messages) { message in
                        MessageBubble(message: message)
                            .id(message.id)
                    }
                    if viewModel.isThinking {
                        ThinkingIndicator()
                            .id("thinking")
                    }
                }
                .padding()
            }
            .accessibilityIdentifier("message_list")
            .onChange(of: viewModel.messages.count) { _ in
                if let last = viewModel.messages.last {
                    withAnimation { proxy.scrollTo(last.id, anchor: .bottom) }
                }
            }
        }
    }

    private var inputBar: some View {
        VStack(spacing: 0) {
            Divider()
            HStack(spacing: 12) {
                TextField("Type a message...", text: $viewModel.inputText)
                    .textFieldStyle(.roundedBorder)
                    .frame(minHeight: 44)
                    .accessibilityIdentifier("text_input_field")
                    .accessibilityLabel("text_input_field")
                    .onSubmit { viewModel.sendText() }

                Button(action: viewModel.sendText) {
                    Image(systemName: "arrow.up.circle.fill")
                        .font(.title2)
                        .foregroundColor(viewModel.inputText.isEmpty ? .gray : .blue)
                }
                .disabled(viewModel.inputText.isEmpty)
                .accessibilityIdentifier("send_text_button")
                .accessibilityLabel("send_text_button")

                Button(action: viewModel.toggleVoice) {
                    Image(systemName: viewModel.isRecording ? "stop.circle.fill" : "mic.circle.fill")
                        .font(.title2)
                        .foregroundColor(viewModel.isRecording ? .red : .blue)
                }
                .accessibilityIdentifier("voice_button")
                .accessibilityLabel("voice_button")
            }
            .padding(.horizontal)
            .padding(.vertical, 10)
            .background(Color(.systemBackground))
        }
    }
}

struct MessageBubble: View {
    let message: ChatMessage

    var body: some View {
        HStack {
            if message.role == .user { Spacer(minLength: 60) }
            VStack(alignment: message.role == .user ? .trailing : .leading, spacing: 3) {
                Text(message.role == .user ? "You" : "Assistant")
                    .font(.caption)
                    .foregroundColor(.secondary)
                Text(message.content)
                    .accessibilityIdentifier(message.role == .user ? "user_message" : "assistant_message")
                    .padding(.horizontal, 12)
                    .padding(.vertical, 8)
                    .background(message.role == .user ? Color.blue : Color(UIColor.secondarySystemBackground))
                    .foregroundColor(message.role == .user ? .white : .primary)
                    .clipShape(RoundedRectangle(cornerRadius: 16))
                    .accessibilityIdentifier("message_bubble_\(message.id)")
            }
            if message.role == .assistant { Spacer(minLength: 60) }
        }
        .accessibilityIdentifier(message.role == .user ? "user_message" : "assistant_message")
    }
}

struct ThinkingIndicator: View {
    @State private var opacity = 0.3

    var body: some View {
        HStack(spacing: 4) {
            ForEach(0..<3) { i in
                Circle().fill(Color.secondary).frame(width: 8, height: 8)
                    .opacity(opacity)
                    .animation(.easeInOut(duration: 0.6).repeatForever().delay(Double(i) * 0.2), value: opacity)
            }
        }
        .padding(.horizontal, 12)
        .padding(.vertical, 8)
        .background(Color(.secondarySystemBackground))
        .clipShape(RoundedRectangle(cornerRadius: 16))
        .onAppear { opacity = 1.0 }
        .accessibilityIdentifier("thinking_indicator")
    }
}
