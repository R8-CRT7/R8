// swift-tools-version:5.9
import PackageDescription

let package = Package(
    name: "Smart360Core",
    platforms: [.iOS(.v17), .macOS(.v14)],
    products: [
        .library(name: "Smart360Core", targets: ["Smart360Core"]),
    ],
    targets: [
        .target(name: "Smart360Core", path: "Sources/Smart360Core"),
        .testTarget(name: "Smart360CoreTests", dependencies: ["Smart360Core"], path: "Tests/Smart360CoreTests"),
    ]
)
