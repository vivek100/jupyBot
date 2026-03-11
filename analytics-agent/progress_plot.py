import matplotlib.pyplot as plt
import numpy as np

# Data from our evaluation runs
runs = [
    ("Baseline (v0)", 21.0, "#ff6b6b"),
    ("v3 (scalar fix)", 74.4, "#4ecdc4"),
    ("v5 (few-shot, 39q)", 89.7, "#45b7d1"),
    ("v6 (100q, random)", 82.0, "#f39c12"),
    ("v7 (refined)", 83.0, "#96ceb4"),
    ("v8 (real-data examples)", 84.0, "#dfe6e9"),
]

# Create the plot
plt.figure(figsize=(12, 8))
x = np.arange(len(runs))
accuracy = [acc for _, acc, _ in runs]
colors = [color for _, _, color in runs]

# Create bars with gradient effect
bars = plt.bar(x, accuracy, color=colors, alpha=0.8, edgecolor='black', linewidth=1.5)

# Add value labels on top of bars
for bar, acc in zip(bars, accuracy):
    plt.text(bar.get_x() + bar.get_width()/2, bar.get_height() + 1,
             f'{acc}%', ha='center', va='bottom', fontweight='bold', fontsize=12)

# Customize the plot
plt.title('Analytics Agent Accuracy Progress\n(21% → 84% with Small Mistral Model)', 
          fontsize=16, fontweight='bold', pad=20)
plt.xlabel('Version', fontsize=14, fontweight='bold')
plt.ylabel('Accuracy (%)', fontsize=14, fontweight='bold')
plt.ylim(0, 100)

# Add grid
plt.grid(axis='y', alpha=0.3, linestyle='--')

# Customize x-axis
plt.xticks(x, [name for name, _, _ in runs], rotation=15, ha='right')

# Add annotations for key improvements
annotations = [
    (1, 74.4, "Fixed scalar output\n& run_python usage", "4x improvement"),
    (2, 89.7, "Added few-shot\nexamples (39q)", "+15.3%"),
    (3, 82.0, "Expanded to 100q\n(randomized)", "-7.7%"),
    (5, 84.0, "Real-data examples\nwith commentary", "+2%"),
]

for idx, acc, text, label in annotations:
    plt.annotate(text, xy=(idx, acc), xytext=(idx, acc - 15),
                arrowprops=dict(arrowstyle='->', color='gray', lw=1.5),
                ha='center', fontsize=10, bbox=dict(boxstyle='round,pad=0.3', 
                facecolor='white', alpha=0.8))

# Add statistics box
stats_text = f"""Total Improvement: +63 percentage points
Relative Improvement: 300% increase
Model: Small Mistral (7B parameters)
Questions evaluated: 100 (final runs)
Key fixes: scalar output, few-shot examples, column selection guidance
Note: v5 used 39 questions; v6+ use 100 randomized questions"""

plt.figtext(0.02, 0.02, stats_text, fontsize=10, 
            bbox=dict(boxstyle='round', facecolor='lightgray', alpha=0.8))

plt.tight_layout()
plt.savefig('accuracy_progress.png', dpi=300, bbox_inches='tight')
plt.show()

print("Progress plot saved as 'accuracy_progress.png'")
