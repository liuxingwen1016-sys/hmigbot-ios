@ObservedV2
export class CounterViewModel {
  @Trace count: number = 0;

  increment(): void {
    if (this.count < 5) {
      this.count += 1;
    }
  }

  resetCount(): void {
    this.count = 0;
  }
}
