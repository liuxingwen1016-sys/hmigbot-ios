#import <UIKit/UIKit.h>
@interface ViewController : UIViewController
@end
@implementation ViewController
- (void)viewDidLoad {
    [super viewDidLoad];
    UILabel *label = [[UILabel alloc] init];
    label.text = @"Native UI";
    [self.view addSubview:label];
}
@end
