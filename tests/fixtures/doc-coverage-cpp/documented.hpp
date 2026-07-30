/// A documented widget with a public run loop.
class Widget {
public:
    /// Run the widget until stopped.
    void run();

private:
    // A plain line comment is NOT a doc comment, and this member is private,
    // so it must never be enumerated as a public unit.
    void secret();
};

/// Add two integers and return the sum.
int add(int a, int b);
