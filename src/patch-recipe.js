const EXCLUDED = ['build', 'release', 'translate-glossary', 'unity-release'];

const RECIPES = {
  otomate: [
    {id: 'filltitles-fill', phase: 'prepare'},
    {id: 'empty-scan', phase: 'check'},
    {id: 'applyvi', phase: 'create'}
  ],
  unity: [
    {id: 'empty-scan', phase: 'check'},
    {id: 'unity-sheetfit', phase: 'check'},
    {id: 'unity-sheet-apply', phase: 'create'}
  ]
};

function recipeFor(engine) {
  const recipe = RECIPES[engine];
  if (!recipe) throw new Error(`No patch recipe for ${engine}`);
  return recipe.map(step => ({...step}));
}

function setupError({projectPath, outputPath, hasGameFiles, hasFonts}) {
  if (!projectPath || !outputPath || !hasGameFiles || !hasFonts) return 'setup';
  return null;
}

function planStep(step, {copyPath, originalPath, outputPath, runDirectory}) {
  let outputs;
  let argv;
  if (step.id === 'applyvi' || step.id === 'unity-sheet-apply') {
    outputs = [outputPath];
    argv = [copyPath, outputPath];
  } else if (step.id === 'filltitles-fill') {
    outputs = [copyPath];
    argv = [copyPath, copyPath];
  } else {
    outputs = [runDirectory];
    argv = [copyPath, runDirectory];
  }
  if (outputs.includes(originalPath)) throw new Error('Original workbook was planned as an output.');
  return {id: step.id, phase: step.phase, argv, outputs};
}

function planCommands({engine, originalPath, copy, outputPath}) {
  if (!copy || !copy.ok) return [];
  return recipeFor(engine).map(step => planStep(step, {
    copyPath: copy.path, originalPath, outputPath, runDirectory: copy.runDirectory
  }));
}

function runRecipe(engine, ctx) {
  const result = {
    complete: false,
    createCalled: false,
    calledIds: [],
    commands: [],
    skip: false,
    error: null,
    runDirectory: null
  };
  if (ctx.missingSetup || (ctx.setup && setupError(ctx.setup))) {
    result.error = 'setup';
    return result;
  }
  const commands = planCommands({
    engine,
    originalPath: ctx.originalPath,
    copy: ctx.copy,
    outputPath: ctx.outputPath
  });
  result.commands = commands;
  if (!ctx.copy || !ctx.copy.ok) return result;
  result.runDirectory = ctx.copy.runDirectory;
  let sawPrepare = false;
  for (const step of recipeFor(engine)) {
    if (sawPrepare && ctx.cancelAfterPrepare) return result;
    if (step.phase === 'create') {
      const blocked = (ctx.findings && ctx.findings.length) || ctx.checkExit || ctx.reportReadable === false;
      if (blocked) return result;
      if (ctx.outputHasPatch && ctx.confirmed !== true) return result;
      result.createCalled = true;
    }
    result.calledIds.push(step.id);
    if (step.phase === 'prepare') sawPrepare = true;
    const ran = ctx.runStep ? ctx.runStep(step) : {code: 0};
    if (ran && ran.code) ctx.checkExit = ran.code;
    if (ran && ran.findings) ctx.findings = ran.findings;
    if (ran && ran.reportReadable === false) ctx.reportReadable = false;
  }
  result.complete = result.createCalled;
  return result;
}

function excludedIds() { return EXCLUDED.slice(); }

module.exports = {recipeFor, planCommands, planStep, runRecipe, setupError, excludedIds, EXCLUDED};
