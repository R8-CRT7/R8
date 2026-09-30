import Smart360Core
import SwiftUI
import UserNotifications

@main
struct Smart360App: App {
    @UIApplicationDelegateAdaptor(AppDelegate.self) private var delegate
    @State private var model = AppModel()
    @Environment(\.scenePhase) private var scenePhase

    var body: some Scene {
        WindowGroup {
            RootView()
                .environment(model)
                .task {
                    AppModel.registerNotificationCategories()
                    _ = try? await UNUserNotificationCenter.current().requestAuthorization(options: [.alert, .sound])
                    delegate.model = model
                }
        }
        .onChange(of: scenePhase) { _, phase in
            if phase == .active {
                model.reloadHistory()  // the broadcast / share extensions may have added entries
                Task { await model.processInbox() }
            }
        }
    }
}

final class AppDelegate: NSObject, UIApplicationDelegate, UNUserNotificationCenterDelegate {
    weak var model: AppModel?

    func application(_ application: UIApplication,
                     didFinishLaunchingWithOptions launchOptions: [UIApplication.LaunchOptionsKey: Any]?) -> Bool {
        UNUserNotificationCenter.current().delegate = self
        return true
    }

    /// CONFIRM / REJECT on a live-result notification: records the user's decision for that entry.
    func userNotificationCenter(_ center: UNUserNotificationCenter, didReceive response: UNNotificationResponse) async {
        guard let idString = response.notification.request.content.userInfo["history_id"] as? String,
              let id = UUID(uuidString: idString) else { return }
        let store = HistoryStore(url: AppGroup.historyURL)
        switch response.actionIdentifier {
        case "CONFIRM": store.setDecision(id, .accepted)
        case "REJECT": store.setDecision(id, .rejected)
        default: break
        }
        await MainActor.run { model?.reloadHistory() }
    }

    func userNotificationCenter(_ center: UNUserNotificationCenter,
                                willPresent notification: UNNotification) async -> UNNotificationPresentationOptions {
        [.banner, .sound]
    }
}
