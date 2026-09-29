import SwiftUI

struct CounterView: View {
    @State private var count: Int = 0

    var body: some View {
        VStack(spacing: 16) {
            Text("Count: \(count)")
            HStack(spacing: 8) {
                Button("Add") { count += 1 }
                Button("Reset") { count = 0 }
            }
        }
        .padding(24)
    }
}
