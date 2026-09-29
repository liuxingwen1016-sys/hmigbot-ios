import { CounterViewModel } from '../viewmodels/CounterViewModel';

@Entry
@ComponentV2
struct CounterPage {
  @Local viewModel: CounterViewModel = new CounterViewModel();

  onAdd(): void {
    this.viewModel.increment();
  }

  onReset(): void {
    this.viewModel.resetCount();
  }

  build() {
    Column({ space: 16 }) {
      Text(`Count: ${this.viewModel.count}`).fontSize(24)
      Button('Add').onClick(() => { this.onAdd(); })
      Button('Reset').onClick(() => { this.onReset(); })
    }
    .width('100%')
    .height('100%')
    .justifyContent(FlexAlign.Center)
    .alignItems(HorizontalAlign.Center)
  }
}
