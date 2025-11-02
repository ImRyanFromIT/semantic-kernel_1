---
document_type: technical_reference
topic: semantic_kernel_processes
framework: semantic_kernel
language: python
version: 1.0
last_updated: 2025-10-26
subtopics:
  - kernel_process_steps
  - event_driven_workflows
  - state_management
  - process_building
  - subprocess_composition
  - error_handling
  - patterns_and_best_practices
---

# Semantic Kernel Processes - Reference

## Core Concepts

**Key Points:**

- Four fundamental concepts: Process, Steps, Events, and State
- All components work together in an event-driven model
- Understanding these concepts is essential for building workflows

**Keywords**: KernelProcess, KernelProcessStep, events, state management, ProcessBuilder, workflow composition

### 1. Process

A `KernelProcess` is a workflow composed of interconnected steps that execute in response to events. Processes are built using the `ProcessBuilder` pattern.

**Key Characteristics:**

- Event-driven execution model
- Supports both synchronous and asynchronous flows
- Can contain nested subprocesses
- Maintains state across multiple executions
- Configurable with `max_supersteps` (default: 100)

### 2. Steps

`KernelProcessStep` objects are the building blocks of a process. Each step:

- Contains one or more kernel functions (decorated with `@kernel_function`)
- Can emit events to trigger other steps
- May maintain internal state
- Has a unique name and optional version metadata

**Step Types:**

- **Stateless Steps**: No internal state, purely functional
- **Stateful Steps**: Maintain state using `KernelProcessStepState[T]`

### 3. Events

Events are the communication mechanism between steps. Events contain:

- **Event ID**: Identifier (typically an Enum value)
- **Data**: Payload passed to the target step
- **Visibility**: `Internal` (default) or `Public` (emitted outside process)

**Event Types:**

- **Input Events**: Trigger process entry points
- **Function Result Events**: Automatically emitted after function execution
- **Custom Events**: Explicitly emitted via `context.emit_event()`
- **Output Events**: Public events from nested processes

### 4. State Management

Steps can maintain state that persists across invocations:

```python
class MyState(KernelBaseModel):
    counter: int = Field(default=0, alias="Counter")
    items: list[str] = Field(default_factory=list, alias="Items")

class MyStep(KernelProcessStep[MyState]):
    state: MyState | None = None

    async def activate(self, state: KernelProcessStepState[MyState]) -> None:
        self.state = state.state
```

## Domain Models

Process examples separate domain data models into a `models/` folder for clean architecture.

**Key Points:**

- Use string enums for type-safe domain models
- Models are JSON serializable by default
- Separating models improves code organization
- Enum values provide IDE autocomplete support

**Keywords**: domain models, enums, type safety, JSON serialization, data models, FoodIngredients, FoodItem

### Enum-Based Models

Domain types are typically implemented as string enums for type safety and JSON serialization:

```python
from enum import Enum

class FoodIngredients(str, Enum):
    POTATOES = "Potatoes"
    FISH = "Fish"
    BUNS = "Buns"

    def to_friendly_string(self) -> str:
        return self.value

class FoodItem(str, Enum):
    POTATO_FRIES = "Potato Fries"
    FRIED_FISH = "Fried Fish"

    def to_friendly_string(self) -> str:
        return self.value
```

**Benefits:** Type-safe, JSON serializable, IDE autocomplete support

**Usage in Steps:**

```python
from models import FoodIngredients

class GatherFishStep(GatherIngredientsStep):
    def __init__(self) -> None:
        super().__init__(FoodIngredients.FISH)
```

**Usage in Routing:**

```python
@kernel_function
async def dispatch_order(self, context: KernelProcessStepContext, food_item: FoodItem):
    if food_item == FoodItem.FRIED_FISH:
        await context.emit_event(DispatchEvents.PrepareFish, data=[])
```

## Common Step Implementations

**Key Points:**

- Six common patterns for implementing process steps
- Range from stateless transformations to complex stateful logic
- Patterns are reusable across different workflows
- Examples demonstrate best practices for each pattern type

**Keywords**: step patterns, stateless steps, stateful steps, resource management, retry logic, conditional routing, event bridging

### Overview of Step Patterns

The examples demonstrate several reusable step patterns that solve common workflow challenges. Each pattern serves a specific purpose:

1. **Stateless Processing** - Simple transformations without state
2. **Stateful with Self-Repair** - Maintain state with auto-recovery
3. **Resource Inventory** - Track consumable resources
4. **Random Failure** - Simulate unreliable operations for testing
5. **External Event Bridge** - Connect subprocess events to parent
6. **Conditional Router** - Dispatch based on input type

### Pattern 1: Stateless Processing Step

Simple transformation without state:

```python
@kernel_process_step_metadata("CutFoodStep.V1")
class CutFoodStep(KernelProcessStep):
    class Functions(Enum):
        ChopFood = "ChopFood"
        SliceFood = "SliceFood"

    class OutputEvents(Enum):
        ChoppingReady = "ChoppingReady"
        SlicingReady = "SlicingReady"

    @kernel_function(name=Functions.ChopFood)
    async def chop_food(self, context: KernelProcessStepContext, food_actions: list[str]):
        food_actions.append(f"{food_actions[0]}_chopped")
        await context.emit_event(CutFoodStep.OutputEvents.ChoppingReady, food_actions)
```

### Pattern 2: Stateful Step with Self-Repair

**Use Case**: Steps that degrade over time and need self-maintenance

Maintains state and handles degradation:

```python
class CutFoodState(KernelBaseModel):
    knife_sharpness: int = Field(default=5, alias="KnifeSharpness")

@kernel_process_step_metadata("CutFoodStep.V2")
class CutFoodWithSharpeningStep(KernelProcessStep[CutFoodState]):
    state: CutFoodState | None = None

    async def activate(self, state: KernelProcessStepState[CutFoodState]) -> None:
        self.state = state.state

    @kernel_function
    async def chop_food(self, context: KernelProcessStepContext, food_actions: list[str]):
        if self.state.knife_sharpness <= 3:
            await context.emit_event(OutputEvents.KnifeNeedsSharpening, food_actions)
            return
        self.state.knife_sharpness -= 1
        await context.emit_event(OutputEvents.ChoppingReady, food_actions)

    @kernel_function
    async def sharpen_knife(self, context: KernelProcessStepContext, food_actions: list[str]):
        self.state.knife_sharpness += 5
        await context.emit_event(OutputEvents.KnifeSharpened, food_actions)
```

### Pattern 3: Resource Inventory Step

**Use Case**: Tracking and managing consumable resources across workflow executions

Tracks consumable resources:

```python
class GatherIngredientsState(KernelBaseModel):
    ingredients_stock: int = Field(default=5, alias="IngredientsStock")

class GatherIngredientsWithStockStep(KernelProcessStep[GatherIngredientsState]):
    ingredient: FoodIngredients
    state: GatherIngredientsState | None = None

    def __init__(self, ingredient: FoodIngredients):
        super().__init__(ingredient=ingredient)

    async def activate(self, state: KernelProcessStepState[GatherIngredientsState]) -> None:
        self.state = state.state

    @kernel_function
    async def gather_ingredients(self, context: KernelProcessStepContext, food_actions: list[str]):
        if self.state.ingredients_stock == 0:
            await context.emit_event(OutputEvents.IngredientsOutOfStock, food_actions)
            return
        self.state.ingredients_stock -= 1
        food_actions.append(f"{self.ingredient.value}_gathered")
        await context.emit_event(OutputEvents.IngredientsGathered, food_actions)
```

### Pattern 4: Random Failure Step

**Use Case**: Simulating unreliable operations for testing retry and error handling logic

Simulates unreliable operations:

```python
@kernel_process_step_metadata("FryFoodStep.V1")
class FryFoodStep(KernelProcessStep):
    random_seed: Random = Field(default_factory=Random)

    @kernel_function
    async def fry_food(self, context: KernelProcessStepContext, food_actions: list[str]):
        if self.random_seed.randint(0, 10) < 5:  # 50% failure rate
            await context.emit_event(OutputEvents.FoodRuined, food_actions)
            return
        food_actions.append(f"{food_actions[0]}_fried")
        await context.emit_event(
            OutputEvents.FriedFoodReady,
            food_actions,
            visibility=KernelProcessEventVisibility.Public
        )
```

### Pattern 5: External Event Bridge

**Use Case**: Exposing internal subprocess events to parent processes for coordination

Exposes subprocess events to parent:

```python
class ExternalStep(KernelProcessStep):
    external_event_name: str

    def __init__(self, external_event_name: str):
        super().__init__(external_event_name=external_event_name)

    @kernel_function()
    async def emit_external_event(self, context: KernelProcessStepContext, data: Any):
        await context.emit_event(
            process_event=self.external_event_name,
            data=data,
            visibility=KernelProcessEventVisibility.Public
        )
```

### Pattern 6: Conditional Router Step

**Use Case**: Routing workflow execution to different paths based on input data

Dispatches based on input type:

```python
class DispatchOrderStep(KernelProcessStep):
    @kernel_function
    async def dispatch_order(self, context: KernelProcessStepContext, food_item: FoodItem):
        if food_item == FoodItem.FRIED_FISH:
            await context.emit_event(OutputEvents.PrepareFriedFish, [])
        elif food_item == FoodItem.POTATO_FRIES:
            await context.emit_event(OutputEvents.PrepareFries, [])
        # ... additional routes
```

## Key Components

**Key Points:**

- Three core components: KernelProcessStep, KernelProcessStepContext, ProcessBuilder
- Each component has a specific role in building and executing processes
- Understanding component APIs is essential for effective workflow development

**Keywords**: KernelProcessStep, KernelProcessStepContext, ProcessBuilder, process execution, kernel functions, event emission

### KernelProcessStep

**Purpose**: Base class for all process steps

Base class for all process steps.

```python
from semantic_kernel.processes.kernel_process import KernelProcessStep, KernelProcessStepContext
from semantic_kernel.functions import kernel_function

class MyStep(KernelProcessStep):
    @kernel_function
    async def my_function(self, context: KernelProcessStepContext, input_data: str):
        # Process data
        result = f"Processed: {input_data}"

        # Emit event to next step
        await context.emit_event(
            process_event=MyStep.OutputEvents.Complete,
            data=result
        )
```

**Key Methods:**

- `activate(state)`: Called when step is initialized, used to set up state
- `create_default_state()`: Optional user-defined helper to initialize default state
- Kernel functions: Business logic decorated with `@kernel_function`

### KernelProcessStepContext

Provides context for step execution with methods:

- `emit_event(process_event, data, visibility)`: Emit events to other steps
- Access kernel by adding a `kernel: Kernel` parameter to your kernel function; the context does not expose a kernel property

### ProcessBuilder

Fluent API for constructing processes:

```python
from semantic_kernel.processes.process_builder import ProcessBuilder

process = ProcessBuilder(name="MyProcess", version="v1")

# Add steps
step1 = process.add_step(Step1)
step2 = process.add_step(Step2)

# Define input event
process.on_input_event(event_id=ProcessEvents.Start).send_event_to(step1)

# Connect steps via events
step1.on_event(Step1.OutputEvents.Complete).send_event_to(step2)
step2.on_event(Step2.OutputEvents.Done).stop_process()

# Build the process
kernel_process = process.build()
```

### Process Execution

Use `start()` to execute a process:

```python
from semantic_kernel.processes.local_runtime.local_kernel_process import start

async with await start(
    process=kernel_process,
    kernel=kernel,
    initial_event=ProcessEvents.Start,  # or "Start"
    data=initial_data,
    max_supersteps=100  # Optional: configure max execution steps
) as process_context:
    final_state = await process_context.get_state()
```

## Building Processes: Patterns and Techniques

**Key Points:**

- Seven fundamental patterns for building process workflows
- Patterns cover linear, branching, looping, and parallel execution
- Each pattern solves specific workflow orchestration challenges
- Patterns can be combined for complex workflows

**Keywords**: linear process, conditional branching, loops, retry logic, parallel execution, subprocess integration, self-referential events, exit conditions

### Pattern 1: Simple Linear Process

**Use Case**: Sequential execution of steps where each step completes before the next begins

Steps execute sequentially:

```python
process = ProcessBuilder("LinearProcess")
step_a = process.add_step(StepA)
step_b = process.add_step(StepB)
step_c = process.add_step(StepC)

process.on_input_event(ProcessEvents.Start).send_event_to(step_a)
step_a.on_event(StepA.OutputEvents.Done).send_event_to(step_b)
step_b.on_event(StepB.OutputEvents.Done).send_event_to(step_c)
step_c.on_event(StepC.OutputEvents.Done).stop_process()
```

### Pattern 2: Conditional Branching

**Use Case**: Routing execution to different paths based on runtime conditions or data

Steps emit different events based on conditions:

```python
# In step function
if condition:
    await context.emit_event(MyStep.OutputEvents.SuccessPath, data)
else:
    await context.emit_event(MyStep.OutputEvents.ErrorPath, data)

# In process builder
my_step.on_event(MyStep.OutputEvents.SuccessPath).send_event_to(success_step)
my_step.on_event(MyStep.OutputEvents.ErrorPath).send_event_to(error_step)
```

### Pattern 3: Loops and Retry Logic

**Use Case**: Implementing retry mechanisms and iterative processing

Steps can emit events back to earlier steps:

```python
gather.on_event(GatherStep.OutputEvents.IngredientsGathered).send_event_to(process_step)
process_step.on_event(ProcessStep.OutputEvents.Failed).send_event_to(gather)  # Retry
```

### Pattern 4: Parallel Execution

**Use Case**: Running independent operations concurrently and combining results (fan-out/fan-in)

Multiple steps triggered by same event (fanout):

```python
process.on_input_event(ProcessEvents.Start)\
    .send_event_to(make_fish_step.where_input_event_is(FishEvents.Start))\
    .send_event_to(make_fries_step.where_input_event_is(FriesEvents.Start))

# Join results
make_fish_step.on_event(FishEvents.Ready).send_event_to(combine_step, parameter_name="fish")
make_fries_step.on_event(FriesEvents.Ready).send_event_to(combine_step, parameter_name="fries")
```

### Pattern 5: Subprocess Integration

**Use Case**: Composing complex workflows from reusable subprocess components

Embed processes as steps within larger processes:

```python
# Create subprocess
fish_process = FriedFishProcess.create_process()

# Add as step
parent_process = ProcessBuilder("ParentProcess")
fish_step = parent_process.add_step_from_process(fish_process)

# Route events to subprocess
parent_process.on_input_event(ParentEvents.Start).send_event_to(
    fish_step.where_input_event_is(FishProcess.ProcessEvents.PrepareFish)
)

# Handle subprocess output
fish_step.on_event(FishProcess.ProcessEvents.FishReady).send_event_to(next_step)
```

### Pattern 6: Self-Referential Events

**Use Case**: Steps that trigger their own functions for multi-phase operations or self-repair

Steps can emit events to themselves (internal loops):

```python
cut_step.on_event(CutStep.OutputEvents.KnifeNeedsSharpening).send_event_to(
    cut_step, function_name=CutStep.Functions.SharpenKnife
)
cut_step.on_event(CutStep.OutputEvents.KnifeSharpened).send_event_to(
    cut_step, function_name=CutStep.Functions.ChopFood
)
```

### Pattern 7: Exit Conditions

**Use Case**: Defining clear termination conditions for process workflows

Use `stop_process()` to terminate:

```python
# Conditional exit
user_input.on_event(ChatEvents.Exit).stop_process()

# Error exit
gather.on_event(GatherStep.OutputEvents.OutOfStock).stop_process()
```

## Event Visibility and External Events

### Internal Events (Default)

Events scoped within the current process. Not visible to parent processes.

### Public Events

Events visible outside the process boundary using `KernelProcessEventVisibility.Public`:

```python
await context.emit_event(
    process_event=MyStep.OutputEvents.Complete,
    data=result,
    visibility=KernelProcessEventVisibility.Public
)
```

### External Step Pattern

Use `ExternalStep` to bridge subprocess events to parent process:

```python
class ExternalStep(KernelProcessStep):
    external_event_name: str

    def __init__(self, external_event_name: str):
        super().__init__(external_event_name=external_event_name)

    @kernel_function()
    async def emit_external_event(self, context: KernelProcessStepContext, data: Any):
        await context.emit_event(
            process_event=self.external_event_name,
            data=data,
            visibility=KernelProcessEventVisibility.Public
        )
```

## State Management

**Key Points:**

- Choose between stateless and stateful steps based on requirements
- Stateful steps use `KernelProcessStepState[T]` for persistence
- Always initialize state in the `activate()` method
- Use field aliases for JSON serialization compatibility

**Keywords**: state management, stateless steps, stateful steps, state persistence, activate method, KernelProcessStepState, field aliases

### How Do I Create Stateless Steps?

**Use Case**: Simple transformations that don't need to remember previous executions

No state persistence between invocations:

```python
class CutFoodStep(KernelProcessStep):
    @kernel_function
    async def chop_food(self, context: KernelProcessStepContext, food: list[str]):
        food.append("chopped")
        await context.emit_event(CutFoodStep.OutputEvents.ChoppingReady, food)
```

### How Do I Maintain State Across Invocations?

**Use Case**: Steps that need to remember data or track changes between executions

Maintain state across invocations:

```python
class CutFoodState(KernelBaseModel):
    knife_sharpness: int = Field(default=5, alias="KnifeSharpness")

class CutFoodWithSharpeningStep(KernelProcessStep[CutFoodState]):
    state: CutFoodState | None = None

    async def activate(self, state: KernelProcessStepState[CutFoodState]) -> None:
        self.state = state.state

    @kernel_function
    async def chop_food(self, context: KernelProcessStepContext, food: list[str]):
        if self.state.knife_sharpness == 0:
            await context.emit_event(CutFoodStep.OutputEvents.NeedsSharpening, food)
            return

        self.state.knife_sharpness -= 1
        food.append("chopped")
        await context.emit_event(CutFoodStep.OutputEvents.ChoppingReady, food)
```

### State Field Aliases

Use `alias` parameter for JSON serialization compatibility:

```python
class MyState(KernelBaseModel):
    counter: int = Field(default=0, alias="Counter")
    items: list[str] = Field(default_factory=list, alias="Items")
```

## State Persistence

**Key Points:**

- Process state can be saved to JSON and restored later
- State includes all step states and subprocess states
- Use `to_process_state_metadata()` to convert state for serialization
- Load state with `KernelProcessStateMetadata.load_from_file()`

**Keywords**: state persistence, save state, load state, JSON serialization, process state metadata, state restoration

### How Do I Save Process State?

**Use Case**: Persisting workflow state to disk for resumption or debugging

Saving process state:

```python
# Execute process and get final state
async with await start(process, kernel, initial_event) as running_process:
    final_state = await running_process.get_state()

# Convert to metadata for serialization
state_metadata = final_state.to_process_state_metadata()

# Save to JSON file
import json
with open("process_state.json", "w") as f:
    json.dump(
        state_metadata.model_dump(exclude_none=True, by_alias=True, mode="json"),
        f,
        indent=4
    )
```

### How Do I Load Previously Saved State?

**Use Case**: Resuming a workflow from a previously saved state

```python
from semantic_kernel.processes.kernel_process import KernelProcessStateMetadata

# Load from file
state_metadata = KernelProcessStateMetadata.load_from_file(
    json_filename="process_state.json",
    directory=Path("./states")
)

# Build process with loaded state
process_with_state = process_builder.build(state_metadata=state_metadata)

# Execute from saved state
async with await start(process_with_state, kernel, initial_event) as running_process:
    pass
```

### State Structure (JSON)

```json
{
  "$type": "Process",
  "id": "unique-id",
  "name": "ProcessName",
  "versionInfo": "v1",
  "stepsState": {
    "StepName": {
      "$type": "Step",
      "id": "step-id",
      "name": "StepName",
      "versionInfo": "v1",
      "state": {
        "KnifeSharpness": 5,
        "IngredientsStock": 10
      }
    },
    "NestedProcess": {
      "$type": "Process",
      "stepsState": {
        /* nested steps */
      }
    }
  }
}
```

## Versioning and Metadata

### Step Metadata Decorator

```python
from semantic_kernel.processes.kernel_process import kernel_process_step_metadata

@kernel_process_step_metadata("CutFoodStep.V2")
class CutFoodWithSharpeningStep(KernelProcessStep):
    pass
```

### Process Versioning

```python
process = ProcessBuilder(name="MyProcess", version="v2.0")
```

### Step Aliases (for backward compatibility)

```python
step = process.add_step(
    MyStep,
    name="newStepName",
    aliases=["oldStepName", "deprecatedStepName"]
)
```

## Routing Events to Functions

**Key Points:**

- Events can target specific functions within a step
- Use `function_name` parameter to route to specific functions
- Parameter mapping allows named arguments from event data
- `on_function_result()` listens for automatic function result events

**Keywords**: event routing, function targeting, parameter mapping, on_function_result, send_event_to

### How Do I Route Events to Specific Functions?

**Use Case**: Targeting a specific function within a step that has multiple functions

Target specific function in step:

```python
gather.on_event(GatherStep.OutputEvents.IngredientsGathered).send_event_to(
    cut_step,
    function_name=CutStep.Functions.SliceFood  # Target specific function
)
```

Note: `on_function_result(...)` listens for the kernel function's registered name (method name or the `@kernel_function(name=...)` override) and hooks into the automatic `<function>.OnResult` events emitted by the runtime after function invocation.

### Parameter Mapping

```python
# Map event data to named parameter
make_fish.on_event(FishEvents.Ready).send_event_to(
    combine_step,
    parameter_name="fishData"
)

# Function signature
@kernel_function
async def combine(self, context: KernelProcessStepContext, fishData: list[str], friesData: list[str]):
    pass
```

## Common Patterns from Examples

**Key Points:**

- Real-world patterns extracted from working examples
- Demonstrate combinations of basic building blocks
- Cover common workflow scenarios: retry, self-repair, routing, inventory
- Patterns are production-ready and can be adapted to different use cases

**Keywords**: gather-process-retry, self-loop, conditional dispatcher, fan-out fan-in, inventory management, chat loop

### Pattern: Gather-Process-Retry

**Use Case**: Collecting resources, processing them, and retrying on failure

Gather ingredients, process them, retry on failure:

```python
# Fried Fish Process
gather = process.add_step(GatherIngredientsStep)
chop = process.add_step(CutFoodStep)
fry = process.add_step(FryFoodStep)

process.on_input_event(ProcessEvents.Start).send_event_to(gather)
gather.on_event(GatherStep.OutputEvents.IngredientsGathered).send_event_to(
    chop, function_name=CutFoodStep.Functions.ChopFood
)
chop.on_event(CutFoodStep.OutputEvents.ChoppingReady).send_event_to(fry)
fry.on_event(FryFoodStep.OutputEvents.FoodRuined).send_event_to(gather)  # Retry
```

### Pattern: Stateful Step with Self-Loop

Step maintains state and handles self-repair:

```python
# Knife sharpening example
cut_step.on_event(CutStep.OutputEvents.ChoppingReady).send_event_to(next_step)
cut_step.on_event(CutStep.OutputEvents.KnifeNeedsSharpening).send_event_to(
    cut_step, function_name=CutStep.Functions.SharpenKnife
)
cut_step.on_event(CutStep.OutputEvents.KnifeSharpened).send_event_to(
    cut_step, function_name=CutStep.Functions.ChopFood
)
```

### Pattern: Conditional Dispatcher

Route to different subprocesses based on input:

```python
@kernel_function
async def dispatch_order(self, context: KernelProcessStepContext, food_item: FoodItem):
    if food_item == FoodItem.FRIED_FISH:
        await context.emit_event(DispatchEvents.PrepareFriedFish, data=[])
    elif food_item == FoodItem.POTATO_FRIES:
        await context.emit_event(DispatchEvents.PrepareFries, data=[])
    # ... more conditions
```

### Pattern: Fan-out/Fan-in (Parallel Processing)

Execute multiple subprocesses, collect results:

```python
# Fan-out
process.on_input_event(ProcessEvents.Start)\
    .send_event_to(fish_process.where_input_event_is(FishEvents.Start))\
    .send_event_to(fries_process.where_input_event_is(FriesEvents.Start))

# Fan-in
fish_process.on_event(FishEvents.Ready).send_event_to(combine_step, parameter_name="fish")
fries_process.on_event(FriesEvents.Ready).send_event_to(combine_step, parameter_name="fries")
```

### Pattern: Stateful Inventory Management

Track resource consumption across process runs:

```python
class GatherIngredientsState(KernelBaseModel):
    ingredients_stock: int = Field(default=5, alias="IngredientsStock")

@kernel_function
async def gather_ingredients(self, context: KernelProcessStepContext, food_actions: list[str]):
    if self.state.ingredients_stock == 0:
        await context.emit_event(GatherStep.OutputEvents.OutOfStock, food_actions)
        return

    self.state.ingredients_stock -= 1
    food_actions.append(f"{ingredient}_gathered")
    await context.emit_event(GatherStep.OutputEvents.IngredientsGathered, food_actions)
```

### Pattern: Chat Loop with Exit Condition

Interactive loop with conditional termination:

```python
process.on_input_event(ChatEvents.Start).send_event_to(intro_step)
intro_step.on_function_result(function_name=IntroStep.print_intro_message.__name__).send_event_to(user_input_step)
user_input_step.on_event(ChatEvents.Exit).stop_process()  # Exit condition
user_input_step.on_event(ChatEvents.UserInput).send_event_to(response_step)
response_step.on_event(ChatEvents.AssistantResponse).send_event_to(user_input_step)  # Loop
```

## Best Practices

**Key Points:**

- Seven categories of best practices covering all aspects of process development
- Follow single responsibility principle for steps
- Minimize state, use aliases, and implement retry logic
- Document flows and ensure proper termination conditions

**Keywords**: best practices, step design, state management, event flow, process composition, testing strategies, performance optimization, error handling

### 1. Step Design

- **Single Responsibility**: Each step should have one clear purpose
- **Stateless Preference**: Use stateless steps unless state is necessary
- **Clear Event Names**: Use descriptive Enum names for events
- **Versioning**: Use `@kernel_process_step_metadata` for version tracking

### 2. State Management

- **Minimal State**: Only persist what's necessary
- **Use Aliases**: Define field aliases for JSON compatibility
- **Activate Pattern**: Always initialize state in `activate()` method
- **Immutable When Possible**: Prefer creating new state objects over mutation

### 3. Event Flow

- **Document Flow**: Use Mermaid diagrams to visualize event flows
- **Visibility Control**: Use `Public` visibility only when needed
- **Error Events**: Define error/failure events for robust handling
- **Avoid Cycles**: Be careful with loops; ensure exit conditions exist

### 4. Process Composition

- **Reusable Subprocesses**: Design processes for composition
- **External Steps**: Use external steps to properly expose subprocess events
- **Naming Convention**: Use consistent naming for processes and steps
- **Version Compatibility**: Use aliases when refactoring step names

### 5. Testing

- **State Snapshots**: Save and test with different state configurations
- **Scripted Inputs**: Use scripted steps for reproducible testing
- **Event Tracing**: Log events for debugging complex flows
- **Max Supersteps**: Configure appropriately to prevent infinite loops

### 6. Performance

- **Parallel Execution**: Use fan-out pattern for independent operations
- **Subprocess Reuse**: Build subprocesses once, reuse multiple times
- **State Size**: Keep state objects small for better serialization performance

### 7. Error Handling

- **Retry Logic**: Implement retry patterns with event loops
- **Graceful Degradation**: Define failure events and fallback paths
- **Resource Limits**: Track resource consumption (inventory, API calls)
- **Stop Conditions**: Always define clear process termination conditions

## Configuration

### Max Supersteps

Controls maximum execution steps to prevent infinite loops:

```python
async with await start(
    process=kernel_process,
    kernel=kernel,
    initial_event=initial_event,
    max_supersteps=50  # Default is 100
) as process_context:
    pass
```

### Kernel Configuration

Processes require a configured Kernel with AI services:

```python
from semantic_kernel import Kernel
from semantic_kernel.connectors.ai.open_ai import OpenAIChatCompletion

kernel = Kernel()
kernel.add_service(OpenAIChatCompletion(service_id="default"))
```

Alternatively, for Azure OpenAI:

```python
from semantic_kernel import Kernel
from semantic_kernel.connectors.ai.open_ai import AzureChatCompletion

kernel = Kernel()
kernel.add_service(AzureChatCompletion(service_id="default"))
```

## Debugging and Troubleshooting

**Key Points:**

- Five common issues with solutions provided
- Six debugging techniques for process workflows
- Use event tracing and state inspection for complex issues
- Mermaid diagrams help visualize flow problems

**Keywords**: debugging, troubleshooting, common issues, process termination, state persistence, event routing, subprocess visibility, deserialization errors

### Common Issues

**Issue**: Process doesn't terminate

- **Cause**: Missing `stop_process()` or exit event
- **Solution**: Ensure all execution paths have termination conditions

**Issue**: State not persisting between runs

- **Cause**: Building new process instances instead of reusing
- **Solution**: Build once, execute multiple times

**Issue**: Events not routing correctly

- **Cause**: Event ID mismatch or missing event handler
- **Solution**: Verify event enum values match between emit and handler

**Issue**: Subprocess events not visible

- **Cause**: Missing `visibility=KernelProcessEventVisibility.Public`
- **Solution**: Use External Step pattern or set visibility

**Issue**: State deserialization errors

- **Cause**: Missing field aliases or incompatible state changes
- **Solution**: Use `alias` parameter and version metadata

### Debugging Techniques

1. **Add Print Statements**: Log step execution and state changes
2. **Event Tracing**: Log all emitted events with their data
3. **State Inspection**: Print state before/after each function
4. **Mermaid Diagrams**: Visualize process flow to identify issues
5. **Step-by-Step Testing**: Test individual steps before integration
6. **State Snapshots**: Save state at various points for comparison

## Example: Complete Process

```python
# Define enums
class ProcessEvents(Enum):
    Start = "Start"
    Complete = "Complete"

# Define state
class CounterState(KernelBaseModel):
    count: int = Field(default=0, alias="Count")

# Define stateful step
class CounterStep(KernelProcessStep[CounterState]):
    state: CounterState | None = None

    async def activate(self, state: KernelProcessStepState[CounterState]) -> None:
        self.state = state.state or CounterState()

    @kernel_function
    async def increment(self, context: KernelProcessStepContext):
        self.state.count += 1
        print(f"Count: {self.state.count}")

        if self.state.count < 5:
            await context.emit_event("Continue", None)
        else:
            await context.emit_event("Done", self.state.count)

# Build process
process = ProcessBuilder("CounterProcess")
counter = process.add_step(CounterStep)

process.on_input_event(ProcessEvents.Start).send_event_to(counter)
counter.on_event("Continue").send_event_to(counter)
counter.on_event("Done").stop_process()

# Execute
kernel = Kernel()
kernel_process = process.build()

async with await start(
    kernel_process,
    kernel,
    initial_event=ProcessEvents.Start
) as ctx:
    final_state = await ctx.get_state()
    print(f"Final count: {final_state}")
```

## Resources

- **Process Framework**: `semantic_kernel/processes/`
- **Kernel Process**: `semantic_kernel/processes/kernel_process/`
- **Local Runtime**: `semantic_kernel/processes/local_runtime/`
- **Examples**: `python/samples/getting_started_with_processes/`

## Summary

Semantic Kernel Processes provides a powerful framework for building complex, event-driven workflows with:

- Modular, reusable step components
- Flexible event-based communication
- Stateful and stateless execution models
- Subprocess composition and nesting
- State persistence and restoration
- Parallel execution patterns
- Robust error handling and retry logic

The framework is ideal for orchestrating multi-step AI workflows, managing conversational flows, implementing business processes, and building complex data pipelines with branching logic and state management requirements.
