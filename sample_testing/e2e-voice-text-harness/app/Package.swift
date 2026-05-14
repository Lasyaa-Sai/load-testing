// swift-tools-version: 5.9
import PackageDescription

let package = Package(
    name: "VoiceTextDemo",
    platforms: [.iOS(.v17)],
    products: [
        .executable(name: "VoiceTextDemo", targets: ["VoiceTextDemo"])
    ],
    targets: [
        .executableTarget(
            name: "VoiceTextDemo",
            path: "Sources/VoiceTextDemo"
        ),
        .testTarget(
            name: "AudioBridgeTests",
            dependencies: ["VoiceTextDemo"],
            path: "Tests/AudioBridgeTests"
        )
    ]
)
