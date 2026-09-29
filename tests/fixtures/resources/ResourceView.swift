import SwiftUI
struct ResourceView: View {
    var body: some View {
        VStack(spacing: 12) {
            Image("Badge")
            Text("Welcome")
            Text(verbatim: "Welcome")
        }.padding(16)
    }
}
