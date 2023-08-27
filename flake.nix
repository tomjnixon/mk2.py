{
  description = "mk2.py";

  inputs = {
    utils.url = "github:numtide/flake-utils";
  };

  outputs = { self, nixpkgs, utils }:
    utils.lib.eachSystem utils.lib.defaultSystems (system:
      let
        pkgs = nixpkgs.legacyPackages."${system}";
        python = pkgs.python311;
      in
      rec {
        packages.mk2_py = pkgs.callPackage ./mk2_py.nix { inherit python; };
        packages.default = packages.mk2_py;

        packages.env = python.withPackages (p: [ packages.mk2_py ]);

        devShells.mk2_py = packages.mk2_py.overridePythonAttrs (attrs: {
          nativeBuildInputs = with python.pkgs; [
            flake8
            black
            isort
            mypy
            pkgs.nixpkgs-fmt
          ];
        });
        devShells.default = devShells.mk2_py;
      }
    );
}
