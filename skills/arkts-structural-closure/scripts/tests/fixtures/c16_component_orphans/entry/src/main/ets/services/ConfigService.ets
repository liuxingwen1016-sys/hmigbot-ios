// VM-side regression control: class used ONLY via static access (no new/getInstance)
// -> instantiation-based orphan check false-flags it; Exemption 4 must exempt it (both sides)
export class ConfigService {
  static get(key: string): string {
    return key
  }
}
