// Parses input data only. It never imports, builds or executes the supplied app.
import Foundation
import SwiftSyntax
import SwiftParser
import SwiftParserDiagnostics

struct SourceInput: Decodable { let path: String; let sha256: String; let source: String }
struct Request: Decodable { let files: [SourceInput] }

final class Collector: SyntaxVisitor {
    let converter: SourceLocationConverter
    var nodes: [[String: Any]] = []
    init(_ tree: SourceFileSyntax, _ path: String) {
        converter = SourceLocationConverter(fileName: path, tree: tree)
        super.init(viewMode: .sourceAccurate)
    }
    func add(_ kind: String, _ node: some SyntaxProtocol, _ value: [String: Any]) {
        let start = node.positionAfterSkippingLeadingTrivia
        let end = node.endPositionBeforeTrailingTrivia
        let location = converter.location(for: start)
        nodes.append(["kind": kind, "start_utf8": start.utf8Offset, "end_utf8": end.utf8Offset,
                      "line": location.line, "column": location.column, "value": value])
    }
    override func visit(_ node: ImportDeclSyntax) -> SyntaxVisitorContinueKind {
        add("import", node, ["module": node.path.trimmedDescription]); return .visitChildren
    }
    override func visit(_ node: StructDeclSyntax) -> SyntaxVisitorContinueKind {
        add("type", node, ["kind": "struct", "name": node.name.text,
            "inherits": node.inheritanceClause?.inheritedTypes.map { $0.type.trimmedDescription } ?? []]); return .visitChildren
    }
    override func visit(_ node: ClassDeclSyntax) -> SyntaxVisitorContinueKind {
        add("type", node, ["kind": "class", "name": node.name.text,
            "inherits": node.inheritanceClause?.inheritedTypes.map { $0.type.trimmedDescription } ?? []]); return .visitChildren
    }
    override func visit(_ node: EnumDeclSyntax) -> SyntaxVisitorContinueKind {
        add("type", node, ["kind": "enum", "name": node.name.text]); return .visitChildren
    }
    override func visit(_ node: ProtocolDeclSyntax) -> SyntaxVisitorContinueKind {
        add("type", node, ["kind": "protocol", "name": node.name.text]); return .visitChildren
    }
    override func visit(_ node: ExtensionDeclSyntax) -> SyntaxVisitorContinueKind {
        add("extension", node, ["type": node.extendedType.trimmedDescription]); return .visitChildren
    }
    override func visit(_ node: FunctionDeclSyntax) -> SyntaxVisitorContinueKind {
        add("function", node, ["name": node.name.text, "signature": node.signature.trimmedDescription]); return .visitChildren
    }
    override func visit(_ node: VariableDeclSyntax) -> SyntaxVisitorContinueKind {
        let bindings = node.bindings.map { binding -> [String: Any] in
            ["pattern": binding.pattern.trimmedDescription,
             "type": binding.typeAnnotation?.type.trimmedDescription ?? "",
             "initializer": binding.initializer?.value.trimmedDescription ?? ""]
        }
        add("variable", node, ["specifier": node.bindingSpecifier.text, "bindings": bindings,
                              "attributes": node.attributes.trimmedDescription]); return .visitChildren
    }
    override func visit(_ node: FunctionCallExprSyntax) -> SyntaxVisitorContinueKind {
        let arguments = node.arguments.map { ["label": $0.label?.text ?? "", "expression": $0.expression.trimmedDescription] }
        add("call", node, ["callee": node.calledExpression.trimmedDescription, "arguments": arguments,
                           "has_trailing_closure": node.trailingClosure != nil]); return .visitChildren
    }
    override func visit(_ node: AttributeSyntax) -> SyntaxVisitorContinueKind {
        add("attribute", node, ["name": node.attributeName.trimmedDescription]); return .visitChildren
    }
    override func visit(_ node: IfConfigDeclSyntax) -> SyntaxVisitorContinueKind {
        add("conditional_compilation", node, ["conditions": node.clauses.map { $0.condition?.trimmedDescription ?? "else" }]); return .visitChildren
    }
}

do {
    let request = try JSONDecoder().decode(Request.self, from: FileHandle.standardInput.readDataToEndOfFile())
    var files: [[String: Any]] = []
    for file in request.files {
        let tree = Parser.parse(source: file.source)
        let collector = Collector(tree, file.path)
        collector.walk(tree)
        let diagnostics = ParseDiagnosticsGenerator.diagnostics(for: tree).map {
            ["message": $0.message, "offset_utf8": $0.position.utf8Offset] as [String: Any]
        }
        files.append(["path": file.path, "sha256": file.sha256, "nodes": collector.nodes,
                      "parse_has_error": tree.hasError, "diagnostics": diagnostics])
    }
    let output: [String: Any] = ["protocol_version": 1, "provider": "SwiftSyntax", "semantic_resolution": false, "files": files]
    let data = try JSONSerialization.data(withJSONObject: output, options: [.sortedKeys])
    FileHandle.standardOutput.write(data)
} catch {
    FileHandle.standardError.write(Data("SwiftSyntax provider error: \(error)\n".utf8))
    exit(2)
}
