const API_URL = "http://localhost:5000/get-elevator-data";
const SENSOR_TYPES = ["temperature", "vibration", "weight", "people_count"];
const maxSamples = 12;
const colors = ["#1f77b4", "#ff7f0e", "#2ca02c", "#d62728"];

const sensorHistory = SENSOR_TYPES.reduce((acc, type) => {
    acc[type] = [];
    return acc;
}, {});

let labels = [];

const charts = {
    temperature: new Chart(document.getElementById("tempChart"), {
        type: "line",
        data: {
            labels: [],
            datasets: [{
                label: "Temperature",
                data: [],
                borderColor: colors[0],
                backgroundColor: `${colors[0]}33`,
                fill: false,
                tension: 0.4,
                pointRadius: 3
            }]
        },
        options: { responsive: true, scales: { y: { beginAtZero: false, title: { display: true, text: '°C' } } } }
    }),
    vibration: new Chart(document.getElementById("vibChart"), {
        type: "line",
        data: {
            labels: [],
            datasets: [{
                label: "Vibration",
                data: [],
                borderColor: colors[1],
                backgroundColor: `${colors[1]}33`,
                fill: false,
                tension: 0.4,
                pointRadius: 3
            }]
        },
        options: { responsive: true, scales: { y: { beginAtZero: true, title: { display: true, text: 'g' } } } }
    }),
    weight: new Chart(document.getElementById("weightChart"), {
        type: "line",
        data: {
            labels: [],
            datasets: [{
                label: "Weight",
                data: [],
                borderColor: colors[2],
                backgroundColor: `${colors[2]}33`,
                fill: false,
                tension: 0.4,
                pointRadius: 3
            }]
        },
        options: { responsive: true, scales: { y: { beginAtZero: true, title: { display: true, text: 'kg' } } } }
    }),
    people_count: new Chart(document.getElementById("peopleChart"), {
        type: "line",
        data: {
            labels: [],
            datasets: [{
                label: "People Count",
                data: [],
                borderColor: colors[3],
                backgroundColor: `${colors[3]}33`,
                fill: false,
                tension: 0.4,
                pointRadius: 3
            }]
        },
        options: { responsive: true, scales: { y: { beginAtZero: true, title: { display: true, text: 'count' } } } }
    })
};

const sensorGrid = document.getElementById("sensorGrid");
const activeSensorsEl = document.getElementById("activeSensors");
const elevatorEl = document.getElementById("elevator");
const lastUpdateEl = document.getElementById("lastUpdate");
const alertBox = document.getElementById("alertBox");

function createSensorCard(sensor) {
    const units = {
        temperature: "°C",
        vibration: "g",
        weight: "kg",
        people_count: ""
    };
    const value = sensor.sensor_value !== null ? sensor.sensor_value + (units[sensor.sensor_type] || "") : "N/A";

    return `
        <div class="sensor-card ${sensor.status.toLowerCase()}">
            <h3>${sensor.sensor_type.replace("_", " ").toUpperCase()}</h3>
            <p><strong>Elevator:</strong> ${sensor.elevator_id}</p>
            <p><strong>Value:</strong> ${value}</p>
            <p><strong>Status:</strong> ${sensor.status}</p>
            <p><strong>Alerts:</strong> ${sensor.alerts.length > 0 ? sensor.alerts.join(", ") : "None"}</p>
        </div>
    `;
}

function buildSensorCards(sensorMap) {
    sensorGrid.innerHTML = SENSOR_TYPES.map(type => {
        const sensor = sensorMap[type] || {
            elevator_id: "ELEVATOR_1",
            sensor_type: type,
            sensor_value: null,
            status: "OFFLINE",
            alerts: []
        };
        return createSensorCard(sensor);
    }).join("");
}

function updateCharts(timeLabel) {
    labels.push(timeLabel);
    if (labels.length > maxSamples) labels.shift();

    SENSOR_TYPES.forEach(type => {
        const chart = charts[type];
        chart.data.labels = [...labels];
        chart.data.datasets[0].data = [...sensorHistory[type]];
        chart.update();
    });
}

function normalizeSensor(sensor, type) {
    return {
        elevator_id: sensor?.elevator_id || "ELEVATOR_1",
        sensor_type: type,
        sensor_value: sensor?.sensor_value ?? null,
        status: sensor?.status ?? "OFFLINE",
        alerts: sensor?.alerts ?? [],
        temperature: sensor?.temperature ?? null,
        vibration: sensor?.vibration ?? null,
        weight: sensor?.weight ?? null,
        people_count: sensor?.people_count ?? 0,
        door_status: sensor?.door_status ?? "offline"
    };
}

async function fetchData() {
    try {
        const res = await fetch(API_URL + "?t=" + new Date().getTime());
        const data = await res.json();

        if (!Array.isArray(data)) {
            throw new Error("Expected an array of sensor records.");
        }

        const sensorMap = data.reduce((acc, sensor) => {
            acc[sensor.sensor_type] = sensor;
            return acc;
        }, {});

        const timestamp = new Date().toLocaleTimeString();
        lastUpdateEl.innerText = timestamp;
        elevatorEl.innerText = "ELEVATOR_1";

        let activeSensors = 0;

        SENSOR_TYPES.forEach(type => {
            const sensor = normalizeSensor(sensorMap[type], type);
            if (sensor.status !== "OFFLINE") activeSensors += 1;

            const value = sensor.sensor_value !== null && sensor.sensor_value !== undefined
                ? Number(sensor.sensor_value)
                : null;
            sensorHistory[type].push(value);
            if (sensorHistory[type].length > maxSamples) {
                sensorHistory[type].shift();
            }
        });

        activeSensorsEl.innerText = `${activeSensors} / ${SENSOR_TYPES.length}`;
        buildSensorCards(sensorMap);
        updateCharts(timestamp);

        const alertList = Object.values(sensorMap).flatMap(sensor => sensor.alerts || []);
        if (alertList.length > 0) {
            alertBox.innerText = "⚠ " + [...new Set(alertList)].join(", ");
            alertBox.style.background = "#ff4d4d";
            alertBox.style.animation = "blink 1s infinite";
        } else {
            alertBox.innerText = "✓ All monitored sensors are operating normally";
            alertBox.style.background = "#2ecc71";
            alertBox.style.animation = "none";
        }
    } catch (err) {
        alertBox.innerText = "Error fetching data: " + err.message;
        alertBox.style.background = "#f39c12";
        alertBox.style.animation = "none";
        console.error("Dashboard fetch error:", err);
    }
}

fetchData();
setInterval(fetchData, 3000);
