export function linspace(start, stop, n) {
  const arr = [];
  if (n <= 1) return [start];
  const step = (stop - start) / (n - 1);
  for (let i = 0; i < n; i++) arr.push(start + i * step);
  return arr;
}

export function clamp(v, min, max) {
  return Math.max(min, Math.min(max, v));
}

export function gradient(y, x) {
  const g = [];
  for (let i = 0; i < y.length; i++) {
    if (i === 0) {
      g.push((y[1] - y[0]) / (x[1] - x[0]));
    } else if (i === y.length - 1) {
      g.push((y[i] - y[i - 1]) / (x[i] - x[i - 1]));
    } else {
      g.push((y[i + 1] - y[i - 1]) / (x[i + 1] - x[i - 1]));
    }
  }
  return g;
}

export function cumulativeTrapezoid(y, x) {
  const area = [0];
  for (let i = 1; i < y.length; i++) {
    const h = x[i] - x[i - 1];
    area.push(area[i - 1] + 0.5 * h * (y[i] + y[i - 1]));
  }
  return area;
}

export function trapezoidIntegral(x, y) {
  let area = 0;
  for (let i = 1; i < x.length; i++) {
    area += 0.5 * (x[i] - x[i - 1]) * (y[i] + y[i - 1]);
  }
  return area;
}

export function simpsonIntegralUniform(x, y) {
  let n = x.length - 1;
  if (n < 2) return trapezoidIntegral(x, y);

  if (n % 2 !== 0) {
    n -= 1;
  }

  const h = x[1] - x[0];
  let area = y[0] + y[n];

  for (let i = 1; i < n; i++) {
    area += (i % 2 === 0 ? 2 : 4) * y[i];
  }

  area *= h / 3;

  if (n < x.length - 1) {
    area += 0.5 * (x[n + 1] - x[n]) * (y[n + 1] + y[n]);
  }

  return area;
}

export function adaptiveSimpson(f, a, b, eps = 1e-6, maxDepth = 20) {
  function simpsonLocal(fn, left, right) {
    const mid = (left + right) / 2;
    return (right - left) / 6 * (fn(left) + 4 * fn(mid) + fn(right));
  }

  function recurse(fn, left, right, tolerance, whole, depth) {
    const mid = (left + right) / 2;
    const l = simpsonLocal(fn, left, mid);
    const r = simpsonLocal(fn, mid, right);
    const delta = l + r - whole;

    if (depth <= 0 || Math.abs(delta) <= 15 * tolerance) {
      return l + r + delta / 15;
    }

    return recurse(fn, left, mid, tolerance / 2, l, depth - 1)
      + recurse(fn, mid, right, tolerance / 2, r, depth - 1);
  }

  const whole = simpsonLocal(f, a, b);
  return recurse(f, a, b, eps, whole, maxDepth);
}

export function normalize(arr) {
  const maxVal = Math.max(...arr.map(v => Math.abs(v)));
  if (maxVal === 0) return arr.map(() => 0);
  return arr.map(v => v / maxVal);
}

export function nearestIndex(arr, value) {
  let best = 0;
  let bestDist = Infinity;

  for (let i = 0; i < arr.length; i++) {
    const d = Math.abs(arr[i] - value);
    if (d < bestDist) {
      bestDist = d;
      best = i;
    }
  }

  return best;
}

export function deterministicNoise(T) {
  return 0.04 * Math.sin(T * 0.17) + 0.02 * Math.sin(T * 0.73);
}

export function movingAverage(arr, windowSize = 9) {
  const out = [];
  const half = Math.floor(windowSize / 2);

  for (let i = 0; i < arr.length; i++) {
    let sum = 0;
    let count = 0;

    for (let j = i - half; j <= i + half; j++) {
      if (j >= 0 && j < arr.length) {
        sum += arr[j];
        count++;
      }
    }

    out.push(sum / count);
  }

  return out;
}

export function rombergIntegration(f, a, b, maxLevel = 6) {
  const R = Array(maxLevel).fill(0).map(() => Array(maxLevel).fill(0));

  let h = b - a;
  R[0][0] = 0.5 * h * (f(a) + f(b));

  for (let i = 1; i < maxLevel; i++) {
    h /= 2;
    let sum = 0;
    const power = Math.pow(2, i - 1);
    for (let k = 1; k <= power; k++) {
      sum += f(a + (2 * k - 1) * h);
    }
    R[i][0] = 0.5 * R[i - 1][0] + h * sum;

    for (let j = 1; j <= i; j++) {
      const power4 = Math.pow(4, j);
      R[i][j] = (power4 * R[i][j - 1] - R[i - 1][j - 1]) / (power4 - 1);
    }
  }

  return R[maxLevel - 1][maxLevel - 1];
}

export function gaussLegendre4(f, a, b, panels = 1) {
  const x = [
    -0.8611363115940526,
    -0.3399810435848563,
    0.3399810435848563,
    0.8611363115940526
  ];
  const w = [
    0.3478548451374538,
    0.6521451548625461,
    0.6521451548625461,
    0.3478548451374538
  ];

  const n = Math.max(1, Math.floor(panels));
  const h = (b - a) / n;
  let area = 0;

  for (let p = 0; p < n; p++) {
    const left = a + p * h;
    const right = left + h;
    const mid = 0.5 * (right + left);
    const half = 0.5 * (right - left);

    let sum = 0;
    for (let i = 0; i < 4; i++) {
      sum += w[i] * f(mid + half * x[i]);
    }

    area += half * sum;
  }

  return area;
}