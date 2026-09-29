import UIKit

final class CounterViewController: UIViewController {
    private var count = 0
    private let countLabel = UILabel()

    override func viewDidLoad() {
        super.viewDidLoad()
        view.backgroundColor = .white
        countLabel.textAlignment = .center
        countLabel.font = .systemFont(ofSize: 24)
        let add = UIButton(type: .system)
        add.setTitle("Add", for: .normal)
        add.addTarget(self, action: #selector(increment), for: .touchUpInside)
        let reset = UIButton(type: .system)
        reset.setTitle("Reset", for: .normal)
        reset.addTarget(self, action: #selector(resetCount), for: .touchUpInside)
        let stack = UIStackView(arrangedSubviews: [countLabel, add, reset])
        stack.axis = .vertical
        stack.spacing = 16
        stack.translatesAutoresizingMaskIntoConstraints = false
        view.addSubview(stack)
        NSLayoutConstraint.activate([
            stack.centerXAnchor.constraint(equalTo: view.centerXAnchor),
            stack.centerYAnchor.constraint(equalTo: view.centerYAnchor)
        ])
        renderCount()
    }

    @objc private func increment() {
        guard count < 5 else { return }
        count += 1
        renderCount()
    }

    @objc private func resetCount() {
        count = 0
        renderCount()
    }

    private func renderCount() {
        countLabel.text = "Count: \(count)"
    }
}
