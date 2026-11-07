-- Pure translation regression, executed with the installed KOReader LuaJIT.
local settings = {language='en_US'}
G_reader_settings={readSetting=function(self,key) return settings[key] end}
local locale=dofile(arg[1])
assert(locale.t('koreader.menu.sync_all')=='Sync everything')
assert(locale.t('koreader.common.book_count',{count=1})=='1 book')
assert(locale.t('koreader.common.book_count',{count=2})=='2 books')
settings.language='it_IT'
assert(locale.t('koreader.menu.sync_all')=='Sincronizza tutto')
settings.language='tr_TR'
assert(locale.t('koreader.menu.sync_all')=='Sync everything')
settings.kolibre_language='it'
assert(locale.t('koreader.menu.sync_all')=='Sincronizza tutto')
settings.kolibre_language='en'
assert(locale.t('koreader.menu.sync_all')=='Sync everything')
print('PASS: English, Italian, fallback, explicit override and plural translation')
