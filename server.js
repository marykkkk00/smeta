const express = require('express');
const multer = require('multer');
const XLSX = require('xlsx');
const cors = require('cors');
const path = require('path');
const fs = require('fs');
const axios = require('axios');

const app = express();
const PORT = 3000;

const SMETA_RU_API_URL = 'https://cs.smetnoedelo.ru/api/';
const SMETA_RU_TOKEN = 'f8jnhskPMwzovgXG5dxtC7VI'; // Ваш токен

app.use(cors());
app.use(express.json());
app.use(express.static('.'));
app.use(express.urlencoded({ extended: true }));

const storage = multer.diskStorage({
  destination: (req, file, cb) => {
    const dir = 'uploads/';
    if (!fs.existsSync(dir)) fs.mkdirSync(dir, { recursive: true });
    cb(null, dir);
  },
  filename: (req, file, cb) => cb(null, Date.now() + '-' + file.originalname)
});

const upload = multer({ 
  storage,
  fileFilter: (req, file, cb) => {
    if (file.originalname.endsWith('.xlsx') || file.originalname.endsWith('.xls')) cb(null, true);
    else cb(new Error('Только Excel файлы разрешены!'));
  },
  limits: { fileSize: 10 * 1024 * 1024 }
});

// Получение данных из smetnoedelo.ru по коду ресурса
async function getResourceData(code) {
  try {
    const response = await axios.get(`${SMETA_RU_API_URL}?token=${SMETA_RU_TOKEN}&base=gesn&code=${code}`);
    if (response.data) {
      return {
        name: response.data.NAME,
        price: response.data.COMPOSITION?.RESOURCES?.[0]?.QUAN || 0,
        url: response.data.URL || `https://cs.smetnoedelo.ru/gesn/gesn${code}.html`
      };
    }
  } catch (err) {
    console.error(`Ошибка API для ${code}:`, err.message);
  }
  return { name: code, price: 0, url: '' };
}

// Извлечение имени материала
function extractMaterialName(row) {
  for (let i = 2; i <= 5; i++) {
    if (row[i] && String(row[i]).trim() !== '') return String(row[i]).trim();
  }
  return 'Неизвестный материал';
}

// Основная обработка Excel
async function processExcel(filePath) {
  const workbook = XLSX.readFile(filePath);
  const sheet = workbook.Sheets[workbook.SheetNames[0]];
  const rawData = XLSX.utils.sheet_to_json(sheet, { header: 1, defval: "" });
  const dataRows = rawData.slice(43);

  const tableData = [];
  const materialsSummary = {};
  const resourcesMap = {}; // группировка по коду

  for (const row of dataRows) {
    if (!row || row.length < 12) continue;

    const itemNumber = row[0];
    const justification = row[1];
    const nameCell = row[2];
    const unit = row[3] || row[6];
    const quantity = parseFloat(row[4] || 0);
    const unitCost = parseFloat(row[5] || 0);
    const totalCost = parseFloat(row[7] || 0);

    if (!itemNumber && !justification) continue;

    const isMaterial = String(nameCell).toLowerCase().includes('м');

    if (isMaterial) {
      const materialName = extractMaterialName(row);
      const code = justification || itemNumber || materialName;
      let apiData = await getResourceData(code);

      // Группировка по коду ресурса
      if (!resourcesMap[code]) {
        resourcesMap[code] = {
          '№ п/п': itemNumber,
          'Обоснование': justification,
          'Наименование работ и затрат': materialName,
          'Единица измерения': unit,
          'Кол-во': 0,
          'На ед. изм.': 0,
          'Всего в тек. цен.': 0,
          'Сметная цена': 0,
          'Цена API': apiData.price,
          'Ссылка на товар': apiData.url,
          'isMaterial': true
        };
      }
      resourcesMap[code]['Кол-во'] += quantity;
      resourcesMap[code]['На ед. изм.'] += unitCost;
      resourcesMap[code]['Всего в тек. цен.'] += totalCost;
      resourcesMap[code]['Сметная цена'] += unitCost;

      // Сумма по цифра-м
      if (justification && /^\d+/.test(justification)) {
        if (!materialsSummary[justification]) materialsSummary[justification] = { total: 0, items: [] };
        materialsSummary[justification].total += totalCost;
        materialsSummary[justification].items.push({ name: materialName, cost: totalCost });
      }
    } else {
      // Работа или другие затраты
      tableData.push({
        '№ п/п': itemNumber,
        'Обоснование': justification,
        'Наименование работ и затрат': nameCell,
        'Единица измерения': unit,
        'Кол-во': quantity,
        'На ед. изм.': unitCost,
        'Всего в тек. цен.': totalCost,
        'Сметная цена': unitCost,
        'Цена API': null,
        'Ссылка на товар': null,
        'isMaterial': false
      });
    }
  }

  // Преобразуем сгруппированные материалы в массив
  const tableMaterials = Object.values(resourcesMap);
  tableData.push(...tableMaterials);

  return {
    tableData,
    materialsSummary: Object.entries(materialsSummary).map(([number, data]) => ({ number, total: data.total, items: data.items })),
    totalMaterialsCost: tableMaterials.reduce((acc, r) => acc + r['Всего в тек. цен.'], 0)
  };
}

// API для загрузки Excel
app.post('/upload_excel', upload.single('file'), async (req, res) => {
  try {
    if (!req.file) return res.status(400).json({ error: 'Файл не загружен' });

    const result = await processExcel(req.file.path);
    fs.unlinkSync(req.file.path);

    res.json({
      success: true,
      tableData: result.tableData,
      materialsSummary: result.materialsSummary,
      totalMaterialsCost: result.totalMaterialsCost,
      stats: {
        totalRows: result.tableData.length,
        materialRows: result.tableData.filter(r => r.isMaterial).length,
        workRows: result.tableData.filter(r => !r.isMaterial).length
      }
    });
  } catch (err) {
    console.error('Ошибка обработки:', err);
    if (req.file && fs.existsSync(req.file.path)) fs.unlinkSync(req.file.path);
    res.status(500).json({ error: 'Ошибка обработки файла', details: err.message });
  }
});

app.get('/', (req, res) => res.sendFile(path.join(__dirname, 'index.html')));
app.listen(PORT, () => console.log(`Сервер запущен на http://localhost:${PORT}`));
