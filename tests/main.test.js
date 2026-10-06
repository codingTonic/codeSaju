import assert from 'node:assert/strict';
import test from 'node:test';

const { PersonalOSStepperHandler } = await import('../frontend/assets/js/main.js');

test('전체 검증 실패 시 최초 오류 단계로 이동한다', () => {
    const handler = Object.create(PersonalOSStepperHandler.prototype);
    const checkedSteps = [];
    handler.currentStep = 6;
    handler.isPartnerFlowEnabled = () => false;
    handler.validateStep = (step) => {
        checkedSteps.push(step);
        return step !== 3;
    };
    handler.updateStepUI = () => {
        handler.updated = true;
    };
    handler.getStepElement = () => ({ querySelector: () => null });
    globalThis.window = { setTimeout: (callback) => callback() };

    assert.equal(handler.validateAllSteps(), false);
    assert.deepEqual(checkedSteps, [1, 2, 3]);
    assert.equal(handler.currentStep, 3);
    assert.equal(handler.updated, true);
});

test('연인 흐름에서는 선택 단계까지 전체 검증한다', () => {
    const handler = Object.create(PersonalOSStepperHandler.prototype);
    const checkedSteps = [];
    handler.isPartnerFlowEnabled = () => true;
    handler.validateStep = (step) => {
        checkedSteps.push(step);
        return true;
    };

    assert.equal(handler.validateAllSteps(), true);
    assert.deepEqual(checkedSteps, [1, 2, 3, 4, 5, 6]);
});
