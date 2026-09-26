import { expect, test } from '@playwright/test'
import { translateText } from '../src/contexts/i18n-context'

test('Russian admin listing actions do not leak Spanish labels', () => {
  const expected: Record<string, string> = {
    'Cerrar': 'Закрыть',
    'Poner en portada': 'Поставить на главную',
    'Cambiar portada': 'Изменить размещение на главной',
    'Quitar portada': 'Убрать с главной',
    'Subir al TOP': 'Поднять в TOP',
    'Cambiar TOP': 'Изменить TOP',
    'Quitar TOP': 'Убрать из TOP',
    'Usuario': 'Пользователь',
    'Bloquear': 'Заблокировать',
    'Desbloquear': 'Разблокировать',
    'Eliminar': 'Удалить',
    'Sin bloqueo administrativo': 'Без административной блокировки',
  }

  for (const [source, translated] of Object.entries(expected)) {
    expect(translateText(source, 'ru'), source).toBe(translated)
  }
})

test('Russian admin dynamic listing state labels are localized', () => {
  expect(translateText('Portada activa · hasta 30 septiembre 2026', 'ru')).toBe('На главной до 30 сентября 2026')
  expect(translateText('TOP activo · hasta 30 septiembre 2026', 'ru')).toBe('TOP активен до 30 сентября 2026')
  expect(translateText('Bloqueado hasta 30 septiembre 2026', 'ru')).toBe('Заблокировано до 30 сентября 2026')
  expect(translateText('0 visitas', 'ru')).toBe('0 просмотров')
})
