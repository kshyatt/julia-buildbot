###############################################################################
# Define everything needed to do per-commit coverage testing on Linux
###############################################################################

# Add a dependent scheduler for running coverage after we build tarballs
julia_coverage_builders = ["coverage_ubuntu14.04-x64"]
julia_coverage_scheduler = Triggerable(name="Julia Coverage Testing", builderNames=julia_coverage_builders)
c['schedulers'].append(julia_coverage_scheduler)

c['schedulers'].append(ForceScheduler(
    name="coverage build",
    builderNames=julia_coverage_builders,
    reason=FixedParameter(name="reason", default=""),
    revision=FixedParameter(name="revision", default=""),
    branch=FixedParameter(name="branch", default=""),
    repository=FixedParameter(name="repository", default=""),
    project=FixedParameter(name="project", default="Coverage"),
    properties=[
        StringParameter(name="url", size=60, default="https://status.julialang.org/download/linux-x86_64"),
    ]
))

run_coverage_cmd = """
import CoverageBase
using Base.Test
CoverageBase.runtests(CoverageBase.testnames())
"""

analyze_cov_cmd = """
import CoverageBase
using Coverage
cd(joinpath(CoverageBase.julia_top()))
results=Coverage.process_folder("base")
"""

submit_cov_cmd = """
using Coverage, CoverageBase, Compat
# Create git_info for Coveralls
git_info = @compat Dict(
    "branch" => Base.GIT_VERSION_INFO.branch,
    "remotes" => [
        @compat Dict(
            "name" => "origin",
            "url" => "https://github.com/JuliaLang/julia.git"
        )
    ],
    "head" => @compat Dict(
        "id" => Base.GIT_VERSION_INFO.commit,
        "message" => "%(prop:commitmessage)s",
        "committer_name" => "%(prop:commitname)s",
        "committer_email" => "%(prop:commitemail)s",
        "author_name" => "%(prop:authorname)s",
        "author_email" => "%(prop:authoremail)s",
    )
)

# Submit to Coveralls
ENV["REPO_TOKEN"] = ENV["COVERALLS_REPO_TOKEN"]
Coveralls.submit_token(results, git_info)

# Submit to codecov
ENV["REPO_TOKEN"] = ENV["CODECOV_REPO_TOKEN"]
Codecov.submit_token(results, Base.GIT_VERSION_INFO.commit, Base.GIT_VERSION_INFO.branch)
"""

# Steps to download a linux tarball, extract it, run coverage on it, and upload coverage stats
julia_coverage_factory = BuildFactory()
julia_coverage_factory.useProgress = True
julia_coverage_factory.addSteps([
    # Clean the place out from previous runs
    ShellCommand(
        name="clean it out",
        command=["/bin/bash", "-c", "rm -rf *"]
    ),

    # Download the appropriate tarball and extract it
    ShellCommand(
        name="download/extract tarball",
        command=["/bin/bash", "-c", Interpolate("curl -L %(prop:url)s | tar zx")],
    ),

    # Find Julia directory (so we don't have to know the shortcommit)
    SetPropertyFromCommand(
        name="Find Julia executable",
        command=["/bin/bash", "-c", "echo julia-*"],
        property="juliadir"
    ),

    # Update packages
    ShellCommand(
        name="Update packages",
        command=[Interpolate("%(prop:juliadir)s/bin/julia"), "-e", "Pkg.update(); Pkg.build()"],
    ),

    # Install Coverage, CoverageBase
    ShellCommand(
        name="Install Coverage and checkout latest master",
        command=[Interpolate("%(prop:juliadir)s/bin/julia"), "-e", "Pkg.add(\"Coverage\"); Pkg.checkout(\"Coverage\", \"master\")"],
    ),
    ShellCommand(
        name="Install CoverageBase and checkout latest master",
        command=[Interpolate("%(prop:juliadir)s/bin/julia"), "-e", "Pkg.add(\"CoverageBase\"); Pkg.checkout(\"CoverageBase\", \"master\")"],
    ),

    # Test CoverageBase to make sure everything's on the up-and-up
    ShellCommand(
        name="Test CoverageBase.jl",
        command=[Interpolate("%(prop:juliadir)s/bin/julia"), "-e", "Pkg.test(\"CoverageBase\")"],
        haltOnFailure=True,
    ),

    # Run Julia, gathering coverage statistics
    ShellCommand(
        name="Run inlined tests",
        command=[Interpolate("%(prop:juliadir)s/bin/julia"), "--precompiled=no", "--code-coverage=all", "-e", run_coverage_cmd]
    ),
    ShellCommand(
        name="Run non-inlined tests",
        command=[Interpolate("%(prop:juliadir)s/bin/julia"), "--precompiled=no", "--code-coverage=all", "--inline=no", "-e", run_coverage_cmd],
        timeout=3600,
    ),
    ShellCommand(
        name="Gather test results",
        command=[Interpolate("%(prop:juliadir)s/bin/julia"), "-e", analyze_cov_cmd]
    ),
    #submit the results!
    ShellCommand(
        name="Submit",
        command=[Interpolate("%(prop:juliadir)s/bin/julia"), "-e", Interpolate(submit_cov_cmd)],
        env={'COVERALLS_REPO_TOKEN':COVERALLS_REPO_TOKEN, 'CODECOV_REPO_TOKEN':CODECOV_REPO_TOKEN},
        logEnviron=False,
    ),
])


# Add coverage builders
c['builders'].append(BuilderConfig(
    name="coverage_ubuntu14.04-x64",
    slavenames=["ubuntu14.04-x64"],
    category="Coverage",
    factory=julia_coverage_factory
))
