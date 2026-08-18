(function () {
  'use strict';
  var canvas = document.getElementById('rrag-particles');
  if (!canvas) return;
  var ctx = canvas.getContext('2d');
  var particles = [];
  var PARTICLE_COUNT = 60;
  var CONNECTION_DIST = 150;
  var HIGHLIGHT_COUNT = 3;

  function resize() {
    var panel = canvas.parentElement;
    canvas.width = panel.offsetWidth;
    canvas.height = panel.offsetHeight;
  }

  function createParticle(i) {
    var isHighlight = i < HIGHLIGHT_COUNT;
    return {
      x: Math.random() * canvas.width,
      y: Math.random() * canvas.height,
      vx: (Math.random() - 0.5) * 0.4,
      vy: (Math.random() - 0.5) * 0.4,
      r: isHighlight ? 3.5 : 1.5 + Math.random() * 1.5,
      color: isHighlight ? 'rgba(48,255,151,' : 'rgba(77,101,255,',
      baseOpacity: isHighlight ? 0.4 : 0.6,
      pulse: isHighlight ? Math.random() * Math.PI * 2 : 0,
      isHighlight: isHighlight
    };
  }

  function init() {
    resize();
    particles = [];
    for (var i = 0; i < PARTICLE_COUNT; i++) {
      particles.push(createParticle(i));
    }
  }

  function draw(time) {
    ctx.clearRect(0, 0, canvas.width, canvas.height);
    var i, j, p, q, dx, dy, dist, opacity;

    // Draw connections
    for (i = 0; i < particles.length; i++) {
      p = particles[i];
      for (j = i + 1; j < particles.length; j++) {
        q = particles[j];
        dx = p.x - q.x;
        dy = p.y - q.y;
        dist = Math.sqrt(dx * dx + dy * dy);
        if (dist < CONNECTION_DIST) {
          opacity = 0.15 * (1 - dist / CONNECTION_DIST);
          ctx.beginPath();
          ctx.moveTo(p.x, p.y);
          ctx.lineTo(q.x, q.y);
          ctx.strokeStyle = 'rgba(168,127,255,' + opacity + ')';
          ctx.lineWidth = 0.8;
          ctx.stroke();
        }
      }
    }

    // Draw particles
    for (i = 0; i < particles.length; i++) {
      p = particles[i];
      // Update position
      p.x += p.vx;
      p.y += p.vy;
      if (p.x < 0 || p.x > canvas.width) p.vx *= -1;
      if (p.y < 0 || p.y > canvas.height) p.vy *= -1;

      // Pulse for highlight particles
      var alpha = p.baseOpacity;
      if (p.isHighlight) {
        p.pulse += 0.02;
        alpha = 0.25 + 0.25 * Math.sin(p.pulse);
      }

      ctx.beginPath();
      ctx.arc(p.x, p.y, p.r, 0, Math.PI * 2);
      ctx.fillStyle = p.color + alpha + ')';
      ctx.fill();

      // Glow for highlight particles
      if (p.isHighlight) {
        ctx.beginPath();
        ctx.arc(p.x, p.y, p.r * 3, 0, Math.PI * 2);
        ctx.fillStyle = p.color + (alpha * 0.15) + ')';
        ctx.fill();
      }
    }

    requestAnimationFrame(draw);
  }

  window.addEventListener('resize', function () {
    resize();
  });

  init();
  requestAnimationFrame(draw);
})();
