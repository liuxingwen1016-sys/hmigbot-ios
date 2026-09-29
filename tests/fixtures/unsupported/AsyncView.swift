import SwiftUI

struct AsyncView: View {
    @State private var message: String = "Loading"
    var body: some View {
        Text(message).task {
            message = await fetchMessage()
        }
    }
}
