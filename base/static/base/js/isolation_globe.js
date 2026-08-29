(function () {
  const instances = document.querySelectorAll("[data-isolation-globe]");
  if (!instances.length) return;

  const EARTH_TEXTURE = "https://cdn.jsdelivr.net/gh/apache/echarts-website@asf-site/examples/data-gl/asset/world.topo.bathy.200401.jpg";

  function markerSize(count, maxCount) {
    if (!maxCount) return 6;
    return 5 + Math.sqrt(count / maxCount) * 18;
  }

  function initEchartsGlobe(root, data) {
    const section = root.closest(".isolation-globe-section") || document;
    const chartNode = root.querySelector(".echarts-globe");
    const caption = section.querySelector("[data-globe-caption]");
    const topList = section.querySelector("[data-globe-top-list]");
    if (!chartNode || !window.echarts) {
      if (caption) caption.textContent = "Globe library could not be loaded.";
      return;
    }

    const points = [...(data.points || [])].filter((point) => point.country && Number(point.count) > 0);
    const maxCount = Math.max(...points.map((point) => Number(point.count)), 1);
    const chart = echarts.init(chartNode);

    if (caption) {
      caption.textContent = `${points.length} countries; ${data.total_georeferenced_microorganisms} country-assigned records; ${data.unmapped_other_microorganisms} grouped as Others.`;
    }
    if (topList) {
      topList.innerHTML = [...points]
        .sort((a, b) => Number(b.count) - Number(a.count))
        .slice(0, 5)
        .map((point) => `<li><strong>${point.country}</strong>: ${point.count}</li>`)
        .join("");
    }

    chart.setOption({
      backgroundColor: "#ffffff",
      tooltip: {
        formatter: (params) => `${params.name}: ${params.data.count} records`,
      },
      globe: {
        baseTexture: EARTH_TEXTURE,
        heightTexture: EARTH_TEXTURE,
        displacementScale: 0,
        shading: "lambert",
        environment: "#ffffff",
        light: {
          main: {
            intensity: 1.35,
            shadow: false,
          },
          ambient: {
            intensity: 0.48,
          },
        },
        postEffect: {
          enable: false,
        },
        viewControl: {
          autoRotate: true,
          autoRotateSpeed: 2.5,
          distance: 155,
          alpha: 24,
          beta: 120,
          rotateSensitivity: 1,
          zoomSensitivity: 0.6,
        },
      },
      series: [{
        name: "PesticideDB isolation countries",
        type: "scatter3D",
        coordinateSystem: "globe",
        blendMode: "source-over",
        symbol: "circle",
        symbolSize: (value, params) => markerSize(params.data.count, maxCount),
        data: points.map((point) => ({
          name: point.country,
          value: [Number(point.lon), Number(point.lat), 0],
          count: Number(point.count),
          itemStyle: {
            color: "rgba(231, 76, 60, 0.88)",
            borderColor: "#ffffff",
            borderWidth: 1,
          },
        })),
        label: {
          show: false,
          formatter: "{b}",
          position: "right",
          distance: 8,
          textStyle: {
            color: "#ffffff",
            fontSize: 18,
            fontWeight: "bold",
            backgroundColor: "rgba(15, 23, 42, 0.9)",
            borderColor: "rgba(255, 255, 255, 0.95)",
            borderWidth: 1,
            borderRadius: 4,
            padding: [5, 8],
          },
        },
        emphasis: {
          label: {
            show: true,
          },
          itemStyle: {
            color: "#ff3b30",
            borderColor: "#ffffff",
            borderWidth: 2,
          },
        },
      }],
    });

    window.addEventListener("resize", () => chart.resize());
  }

  instances.forEach((root) => {
    const url = root.getAttribute("data-globe-data-url");
    if (!url) return;
    fetch(url)
      .then((response) => response.json())
      .then((data) => initEchartsGlobe(root, data))
      .catch(() => {
        const section = root.closest(".isolation-globe-section") || document;
        const caption = section.querySelector("[data-globe-caption]");
        if (caption) caption.textContent = "Globe data could not be loaded.";
      });
  });
})();
