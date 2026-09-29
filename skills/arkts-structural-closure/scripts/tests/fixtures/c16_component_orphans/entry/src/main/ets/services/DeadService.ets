// VM-side regression control: true orphan service (zero usage evidence) -> must stay flagged (both sides)
export class DeadService {
  fetchAll(): string[] {
    return []
  }
}
