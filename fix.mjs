import fs from 'fs';

let content = fs.readFileSync('static/js/dashboard.js', 'utf8');

// Replace exact broken strings found in the file
content = content.replace(/Р’ СЃРµС‚и/g, "В сети");
content = content.replace(/Р”РћР‘РђР’Р˜РўР¬ Р’ Р”Р РЈР—Р¬РЇ/g, "ДОБАВИТЬ В ДРУЗЬЯ");
content = content.replace(/Р’С‹ РјРѕР¶РµС‚Рµ РґРѕР±Р°РІиС‚СЊ РґСЂСѓР·РµР№ РїРѕ иРјРµРЅи РїРѕР»СЊР·РѕРІР°С‚РµР»СЏ\./g, "Вы можете добавить друзей по имени пользователя.");
content = content.replace(/ВВведите имя пользователя/g, "Введите имя пользователя");

fs.writeFileSync('static/js/dashboard.js', content, 'utf8');
console.log("Fixed dashboard.js!");
