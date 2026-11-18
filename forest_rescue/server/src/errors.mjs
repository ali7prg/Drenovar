// Contract error codes (CONTRACT.md §6) with Russian UI messages, and the mapping of
// error codes thrown by the delivered reference modules onto them.
import {data} from './vendor.mjs';

const ui = data.uiRu.strings;
const introTexts = data.unlockIntro.texts;

export const MESSAGES_RU = Object.freeze({
  FOREST_LOCKED_HALL_LEVEL: introTexts['error.forestLocked'],
  HALL_LEVEL_TOO_LOW: 'Нужна ратуша уровня {level}. Полученные награды уже сохранены в резерве.',
  CAMPAIGN_PAUSED: 'Приключение свёрнуто. Нажмите «Продолжить приключение», чтобы снова выполнять задания. Награды можно забирать и сейчас.',
  TASK_OUT_OF_ORDER: 'Это задание пока недоступно: сначала выполните предыдущие шаги этого места.',
  ACT_LOCKED: ui['act.locked'],
  NOT_ARRIVED: 'Отряд ещё не дошёл до нужной точки. Дождитесь прибытия.',
  TARGET_UNKNOWN: 'Это место пока неизвестно. Исследуйте лес дальше.',
  SQUAD_EMPTY: 'Сначала соберите отряд из свободных воинов.',
  SQUAD_BUSY: 'Отряд занят: дождитесь окончания боя или сопровождения.',
  MECHANISM_NOT_READY: 'Механизм ещё не готов. Выполните условия этого места.',
  PLATES_NOT_OCCUPIED: ui['mechanism.paired'],
  NO_BATTLE_PROOF: ui['error.unverifiedBattle'],
  ARTIFACT_MISSING: ui['artifact.missing'],
  ESCORT_NOT_ARRIVED: 'Люди ещё в пути. Задание завершится после их прибытия домой.',
  BOSS_LOCKED: ui['boss.locked'],
  IDEMPOTENCY_BODY_MISMATCH: ui['error.replayConflict'],
  BAD_FIELDS: 'Неверный формат команды приключения. Обновите игру.',
  STATE_CORRUPT: 'Сохранение приключения повреждено. Изменения не применены, данные не удалены.',
  SCHEMA_UNSUPPORTED: ui['error.version'],
  CAS_CONFLICT_RETRY: 'Состояние изменилось одновременно в другой вкладке. Повторите запрос.',
  // Additive codes (CONTRACT.md changelog v1.1).
  GUARDIAN_DEFEATED: 'Страж этого места уже побеждён и больше не появится.',
  UNITS_UNAVAILABLE: 'Столько свободных здоровых воинов нет. Отряд представляет только настоящую армию.',
  INTRO_NOT_SAFE: 'Вступление можно будет показать после завершения боя.',
  INTRO_STALE_ATTEMPT: 'Это вступление уже завершено или устарело. Обновите состояние.',
});

export const STATUS = Object.freeze({
  BAD_FIELDS: 400,
  FOREST_LOCKED_HALL_LEVEL: 403,
  HALL_LEVEL_TOO_LOW: 403,
  TARGET_UNKNOWN: 404,
});

export class AdventureError extends Error {
  constructor(code, {message, detail, status} = {}) {
    super(code);
    this.code = code;
    this.status = status ?? STATUS[code] ?? 409;
    this.ruMessage = message ?? MESSAGES_RU[code] ?? MESSAGES_RU.BAD_FIELDS;
    if (detail !== undefined) this.detail = detail;
  }
  toBody() {
    const body = {error: this.code, message: this.ruMessage};
    if (this.detail !== undefined) body.detail = this.detail;
    return body;
  }
}

export function fail(code, options) {
  throw new AdventureError(code, options);
}

export function hallMessage(level) {
  return MESSAGES_RU.HALL_LEVEL_TOO_LOW.replace('{level}', String(level));
}

const DOMAIN_MAP = {
  CAMPAIGN_PAUSED: 'CAMPAIGN_PAUSED',
  TASK_ORDER: 'TASK_OUT_OF_ORDER',
  HORSE_REQUIRED: 'TASK_OUT_OF_ORDER',
  BOSS_NOT_ACTIVE: 'TASK_OUT_OF_ORDER',
  MECHANISM_ACCESS_DENIED: 'TASK_OUT_OF_ORDER',
  PREVIOUS_ACT_REQUIRED: 'ACT_LOCKED',
  UNVERIFIED_ARRIVAL: 'NOT_ARRIVED',
  UNVERIFIED_MECHANISM: 'MECHANISM_NOT_READY',
  LANDMARK_NOT_REACHED: 'MECHANISM_NOT_READY',
  PLATES_NOT_SIMULTANEOUS: 'PLATES_NOT_OCCUPIED',
  UNVERIFIED_BATTLE: 'NO_BATTLE_PROOF',
  BATTLE_PROOF_REUSED: 'NO_BATTLE_PROOF',
  ARTIFACT_REQUIRED: 'ARTIFACT_MISSING',
  UNVERIFIED_ESCORT: 'ESCORT_NOT_ARRIVED',
  ALL_RESCUES_REQUIRED: 'BOSS_LOCKED',
  INVALID_ACTION: 'BAD_FIELDS',
  UNKNOWN_ACTION: 'BAD_FIELDS',
  UNKNOWN_TASK: 'BAD_FIELDS',
  UNKNOWN_SITE: 'BAD_FIELDS',
  INVALID_INTRO_ACTION: 'BAD_FIELDS',
  INVALID_MECHANISM_INPUT: 'BAD_FIELDS',
  INTRO_NOT_SAFE: 'INTRO_NOT_SAFE',
  STALE_INTRO_ATTEMPT: 'INTRO_STALE_ATTEMPT',
};

const DOMAIN_MESSAGES = {
  HORSE_REQUIRED: 'Сначала найдите Искру у северного выхода из поселения.',
  BOSS_NOT_ACTIVE: 'Сначала войдите в Костяную чашу.',
  MECHANISM_ACCESS_DENIED: 'Сначала обнаружьте это место и приведите туда отряд.',
  LANDMARK_NOT_REACHED: 'Отряд ещё не прошёл мимо этой приметы. Пройдите по следу.',
  PLATES_NOT_SIMULTANEOUS: MESSAGES_RU.PLATES_NOT_OCCUPIED,
  BATTLE_PROOF_REUSED: 'Этот боевой отчёт уже использован. Награда не выдана повторно.',
};

/**
 * Convert any error thrown inside the adventure transaction to an AdventureError.
 * `scope` distinguishes hall requirements of the gate (forest access) from higher
 * guardian/boss requirements (HALL_LEVEL_TOO_LOW).
 */
export function toAdventureError(error, {requiredHall} = {}) {
  if (error instanceof AdventureError) return error;
  const code = error?.code ?? error?.message;
  if (code === 'HALL_REQUIRED' || code === 'INVALID_HALL_LEVEL') {
    if (requiredHall && requiredHall > 3) return new AdventureError('HALL_LEVEL_TOO_LOW', {message: hallMessage(requiredHall), detail: {requiredHall}});
    return new AdventureError('FOREST_LOCKED_HALL_LEVEL', {detail: {requiredHall: 3}});
  }
  if (code === 'FOREST_LOCKED_HALL_LEVEL') return new AdventureError('FOREST_LOCKED_HALL_LEVEL');
  if (DOMAIN_MAP[code]) {
    return new AdventureError(DOMAIN_MAP[code], {message: DOMAIN_MESSAGES[code], detail: {reason: code}});
  }
  if (typeof code === 'string' && /UNSUPPORTED/.test(code)) return new AdventureError('SCHEMA_UNSUPPORTED', {detail: {reason: code}});
  if (typeof code === 'string' && /^(INVALID|REVISION_EXHAUSTED|RESOURCE_OVERFLOW|CURSOR|TRAVERSAL|UNVERIFIED_TRAVERSAL|NAV_)/.test(code)) {
    return new AdventureError('STATE_CORRUPT', {detail: {reason: code}});
  }
  // Programming errors are never disguised as player data corruption.
  const wrapped = new AdventureError('INTERNAL_ERROR', {status: 500, message: 'Внутренняя ошибка сервера приключения. Изменения не применены.'});
  wrapped.cause = error;
  wrapped.internal = true;
  return wrapped;
}
