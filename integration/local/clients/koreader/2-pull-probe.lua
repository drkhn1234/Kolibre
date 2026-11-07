local UIManager=require('ui/uimanager')
local root=require('datastorage'):getDataDir()
UIManager:scheduleIn(2,function()
    local ok,err=xpcall(function()
        local ui=require('apps/filemanager/filemanager').instance
        local plugin=assert(ui.kolibre,'Kolibre plugin not loaded')
        plugin._confirmDownloads=function(self,sends,interactive,proceed) proceed() end
        plugin:_syncNowRun(false,'manual',false,false)
        local file=G_reader_settings:readSetting('kolibre_books_dir')..'/Synthetic Author/Flatpak sync test.epub'
        plugin:_autoPullAllProgress()
        local sidecar=require('docsettings'):open(file)
        assert(sidecar:readSetting('percent_finished')==0.62,'Server progress did not reach KOReader')
        local out=assert(io.open(root..'/result.txt','w'));out:write('PASS: server 62% progress pulled into actual KOReader sidecar\n');out:close()
    end,debug.traceback)
    if not ok then local out=io.open(root..'/result.txt','w');out:write(err);out:close() end
    UIManager:scheduleIn(2,function() UIManager:quit() end)
end)
