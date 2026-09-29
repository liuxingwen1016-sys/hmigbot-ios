"""Create the checked-in generic native iOS fixture (no third-party generator)."""
import hashlib
import json
from pathlib import Path
import shutil

ROOT = Path(__file__).resolve().parents[1]
DEST = ROOT / 'tests/fixtures/cloud_counter'


def main():
    DEST.mkdir(parents=True, exist_ok=True)
    objects = {}
    def uid(key):
        return hashlib.sha256(key.encode()).hexdigest()[:24].upper()
    def obj(key, isa, **values):
        objects[uid(key)] = {'isa': isa, **values}
        return uid(key)
    def config(name, values):
        refs = [obj(name + c, 'XCBuildConfiguration', name=c, buildSettings=values) for c in ('Debug', 'Release')]
        return obj(name, 'XCConfigurationList', buildConfigurations=refs, defaultConfigurationIsVisible=0, defaultConfigurationName='Release')
    def serialize(value):
        if isinstance(value, dict):
            return '{\n' + ''.join(serialize(k) + ' = ' + serialize(v) + ';\n' for k, v in value.items()) + '}'
        if isinstance(value, list):
            return '(' + ''.join(serialize(v) + ',' for v in value) + ')'
        return json.dumps(value, ensure_ascii=False)
    (DEST / 'App.swift').write_text('''import SwiftUI
@main
struct NativeCounterApp: App {
    var body: some Scene { WindowGroup { CounterView() } }
}
''', encoding='utf-8')
    shutil.copyfile(ROOT / 'tests/fixtures/swiftui_counter/CounterView.swift', DEST / 'CounterView.swift')
    sources = []
    refs = []
    for file in ('App.swift', 'CounterView.swift'):
        ref = obj(file, 'PBXFileReference', lastKnownFileType='sourcecode.swift', path=file, sourceTree='<group>')
        refs.append(ref)
        sources.append(obj('build' + file, 'PBXBuildFile', fileRef=ref))
    product = obj('product', 'PBXFileReference', explicitFileType='wrapper.application', path='NativeCounter.app', sourceTree='BUILT_PRODUCTS_DIR')
    products = obj('products', 'PBXGroup', children=[product], name='Products', sourceTree='<group>')
    group = obj('group', 'PBXGroup', children=refs + [products], sourceTree='<group>')
    source_phase = obj('sources', 'PBXSourcesBuildPhase', buildActionMask=2147483647, files=sources, runOnlyForDeploymentPostprocessing=0)
    frameworks = obj('frameworks', 'PBXFrameworksBuildPhase', buildActionMask=2147483647, files=[], runOnlyForDeploymentPostprocessing=0)
    target = obj('target', 'PBXNativeTarget', name='NativeCounter', productName='NativeCounter', productReference=product,
        productType='com.apple.product-type.application', buildPhases=[source_phase, frameworks], buildRules=[], dependencies=[],
        buildConfigurationList=config('targetconfigs', {'PRODUCT_NAME': '$(TARGET_NAME)', 'PRODUCT_BUNDLE_IDENTIFIER': 'com.hmigbot.fixture.counter',
        'GENERATE_INFOPLIST_FILE': 'YES', 'INFOPLIST_KEY_UILaunchScreen_Generation': 'YES', 'INFOPLIST_KEY_UIApplicationSceneManifest_Generation': 'YES',
        'CURRENT_PROJECT_VERSION': '1', 'MARKETING_VERSION': '1.0', 'TARGETED_DEVICE_FAMILY': '1,2', 'SWIFT_EMIT_LOC_STRINGS': 'YES'}))
    project_id = obj('project', 'PBXProject', attributes={'LastUpgradeCheck': '1600'},
        buildConfigurationList=config('projectconfigs', {'SWIFT_VERSION': '5.0', 'IPHONEOS_DEPLOYMENT_TARGET': '17.0', 'SDKROOT': 'iphoneos',
        'CLANG_ENABLE_MODULES': 'YES', 'CLANG_ENABLE_OBJC_ARC': 'YES', 'SWIFT_OPTIMIZATION_LEVEL': '-Onone'}),
        compatibilityVersion='Xcode 14.0', developmentRegion='en', knownRegions=['en', 'Base'], mainGroup=group,
        productRefGroup=products, projectDirPath='', projectRoot='', targets=[target])
    project = DEST / 'NativeCounter.xcodeproj'
    project.mkdir(exist_ok=True)
    (project / 'project.pbxproj').write_text('// !$*UTF8*$!\n' + serialize({'archiveVersion': 1, 'classes': {}, 'objectVersion': 56,
        'objects': objects, 'rootObject': project_id}) + '\n', encoding='utf-8', newline='\n')
    scheme = project / 'xcshareddata/xcschemes'
    scheme.mkdir(parents=True, exist_ok=True)
    ref = f'<BuildableReference BuildableIdentifier="primary" BlueprintIdentifier="{target}" BuildableName="NativeCounter.app" BlueprintName="NativeCounter" ReferencedContainer="container:NativeCounter.xcodeproj"/>'
    (scheme / 'NativeCounter.xcscheme').write_text(f'''<?xml version="1.0" encoding="UTF-8"?>
<Scheme LastUpgradeVersion="1600" version="1.3">
 <BuildAction parallelizeBuildables="YES" buildImplicitDependencies="YES"><BuildActionEntries>
  <BuildActionEntry buildForTesting="YES" buildForRunning="YES" buildForProfiling="YES" buildForArchiving="YES" buildForAnalyzing="YES">{ref}</BuildActionEntry>
 </BuildActionEntries></BuildAction>
 <LaunchAction buildConfiguration="Debug" selectedDebuggerIdentifier="Xcode.DebuggerFoundation.Debugger.LLDB" selectedLauncherIdentifier="Xcode.IDEFoundation.Launcher.LLDB" launchStyle="0" useCustomWorkingDirectory="NO" ignoresPersistentStateOnLaunch="NO" debugDocumentVersioning="YES" debugServiceExtension="internal" allowLocationSimulation="YES"><BuildableProductRunnable runnableDebuggingMode="0">{ref}</BuildableProductRunnable></LaunchAction>
 <ProfileAction buildConfiguration="Release" shouldUseLaunchSchemeArgsEnv="YES" savedToolIdentifier="" useCustomWorkingDirectory="NO" debugDocumentVersioning="YES"><BuildableProductRunnable runnableDebuggingMode="0">{ref}</BuildableProductRunnable></ProfileAction>
 <AnalyzeAction buildConfiguration="Debug"/>
 <ArchiveAction buildConfiguration="Release" revealArchiveInOrganizer="YES"/>
</Scheme>
''', encoding='utf-8', newline='\n')
    print(DEST)


if __name__ == '__main__':
    main()
