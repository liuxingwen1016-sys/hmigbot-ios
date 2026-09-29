// Control (positive on incumbent): unreferenced component under /components/ — incumbent must flag this
@ComponentV2
export struct OrphanCard {
  build() {
    Column() {
      Text('orphan card')
    }
  }
}
