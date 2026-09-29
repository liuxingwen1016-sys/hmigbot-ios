// D-anchor fixture: unreferenced dialog component under /dialogs/ (no importer anywhere)
@CustomDialog
export struct PrivacyPolicyDialog {
  controller: CustomDialogController = new CustomDialogController({ builder: PrivacyPolicyDialog() })

  build() {
    Column() {
      Text('隐私政策')
      Button('同意').onClick(() => { this.controller.close() })
    }
  }
}
