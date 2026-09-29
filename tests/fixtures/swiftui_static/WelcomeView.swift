import SwiftUI

struct WelcomeView: View {
    var body: some View {
        VStack(spacing: 12) {
            Text(verbatim: "Welcome")
            Divider()
            HStack(spacing: 8) {
                Text("Native iOS")
                Spacer()
                Text("HarmonyOS")
            }
        }.padding(16).frame(width: 320, height: 480)
    }
}
