#import <Foundation/Foundation.h>
void invoke(id receiver) {
    [receiver performSelector:NSSelectorFromString(@"dynamicAction")];
}
