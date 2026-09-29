__attribute__((objc_root_class))
@interface Counter
@property(nonatomic) int value;
- (int)add:(int)amount;
@end

@implementation Counter
- (int)add:(int)amount {
    self.value = self.value + amount;
    return self.value;
}
@end
