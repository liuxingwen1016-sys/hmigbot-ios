import { UsedCard } from '../components/UsedCard'
import { ConfirmDialog } from '../dialogs/ConfirmDialog'
import { ConfigService } from '../services/ConfigService'

@Entry
@ComponentV2
struct Index {
  build() {
    Column() {
      Text(ConfigService.get('title'))
      UsedCard()
      ConfirmDialog()
    }
  }
}
