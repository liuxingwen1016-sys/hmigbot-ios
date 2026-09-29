import SwiftUI
import UIKit

struct LegacyContainer: UIViewControllerRepresentable {
    func makeUIViewController(context: Context) -> UIViewController { UIViewController() }
    func updateUIViewController(_ controller: UIViewController, context: Context) {}
}
