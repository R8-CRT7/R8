import Foundation

/// iOS analysis flow. iOS cannot control other apps, so "confirm" records the user's decision
/// (and never triggers input). The same rule as on Windows still holds: a confirmation is only
/// accepted for the question that is *currently* awaiting confirmation.
public enum AnalysisState: String, Codable, Sendable {
    case idle, capturing, analyzing, awaitingConfirmation, confirmed, rejected, paused, error
}

public enum StateMachineError: Error, Equatable {
    case illegalTransition(from: AnalysisState, to: AnalysisState)
    case staleQuestion
    case nothingToConfirm
}

public final class AnalysisStateMachine: @unchecked Sendable {
    private let lock = NSLock()
    public private(set) var state: AnalysisState = .idle
    public private(set) var questionID: String?
    public private(set) var generation = 0

    private static let allowed: [AnalysisState: Set<AnalysisState>] = [
        .idle: [.capturing],
        .capturing: [.analyzing, .idle, .error],
        .analyzing: [.awaitingConfirmation, .idle, .error, .capturing],
        .awaitingConfirmation: [.capturing, .idle],  // confirmed/rejected only via confirm()/reject()
        .confirmed: [.capturing, .idle],
        .rejected: [.capturing, .idle],
        .paused: [],
        .error: [.idle, .capturing],
    ]

    public init() {}

    public func canTransition(to target: AnalysisState) -> Bool {
        lock.lock(); defer { lock.unlock() }
        return Self.allowed[state]?.contains(target) ?? false
    }

    /// Generic transition. Can never enter `.confirmed` / `.rejected` (only confirm()/reject()).
    public func transition(to target: AnalysisState) throws {
        lock.lock(); defer { lock.unlock() }
        guard target != .confirmed, target != .rejected,
              Self.allowed[state]?.contains(target) ?? false else {
            throw StateMachineError.illegalTransition(from: state, to: target)
        }
        if target == .capturing { generation += 1; questionID = nil }
        state = target
    }

    @discardableResult
    public func beginCapture() throws -> Int {
        try transition(to: .capturing)
        lock.lock(); defer { lock.unlock() }
        return generation
    }

    public func questionDetected(_ id: String, generation gen: Int) throws {
        lock.lock(); defer { lock.unlock() }
        guard gen == generation, state == .capturing else { throw StateMachineError.staleQuestion }
        questionID = id
        state = .analyzing
    }

    public func predictionReady(for id: String, generation gen: Int) throws {
        lock.lock(); defer { lock.unlock() }
        guard gen == generation, id == questionID, state == .analyzing else { throw StateMachineError.staleQuestion }
        state = .awaitingConfirmation
    }

    public func confirm(_ id: String) throws {
        lock.lock(); defer { lock.unlock() }
        guard state == .awaitingConfirmation else { throw StateMachineError.nothingToConfirm }
        guard id == questionID else { throw StateMachineError.staleQuestion }
        state = .confirmed
    }

    public func reject(_ id: String) throws {
        lock.lock(); defer { lock.unlock() }
        guard state == .awaitingConfirmation else { throw StateMachineError.nothingToConfirm }
        guard id == questionID else { throw StateMachineError.staleQuestion }
        state = .rejected
    }

    public func pause() {
        lock.lock(); defer { lock.unlock() }
        generation += 1
        questionID = nil
        state = .paused
    }

    public func resume() {
        lock.lock(); defer { lock.unlock() }
        if state == .paused { state = .idle }
    }

    public func fail() {
        lock.lock(); defer { lock.unlock() }
        if state != .paused { generation += 1; state = .error }
    }
}
